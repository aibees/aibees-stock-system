import logging
import time
import anthropic
from app.config.anthropicConfig import anthropic_settings

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_MAX_TOKENS = 8096

# stock-analysis 결과 캐시: {cache_key: {"result": ..., "cached_at": float}}
_CACHE: dict = {}
CACHE_TTL_SECONDS = 3600  # 1시간


class AnthropicService:
    """
    anthropic.Anthropic() 클라이언트를 단일 인스턴스로 유지하는 서비스.
    모듈 레벨에서 한 번만 인스턴스화하여 재사용한다.
    """

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=anthropic_settings.secret_key)

    # ── 기본 메시지 ──────────────────────────────────────────────────────────────

    def chat(self, messages: list[dict], model: str = DEFAULT_MODEL,
        system: str | None = None, max_tokens: int = DEFAULT_MAX_TOKENS,
        cache_key: str | None = None, use_web_search: bool = False,
    ) -> dict:
        """
        단순 요청/응답.
        messages: [{"role": "user", "content": "..."}]
        반환: {"role": "assistant", "content": "..."}
        cache_key: 지정 시 인메모리 캐시(1시간) 사용
        use_web_search: True일 때만 web_search 툴 추가 (기본 False — 토큰 절약)
        """
        # 캐시 히트 확인
        if cache_key:
            entry = _CACHE.get(cache_key)
            if entry and (time.time() - entry["cached_at"]) < CACHE_TTL_SECONDS:
                logger.info("Cache hit for key: %s", cache_key)
                return entry["result"]

        kwargs = dict(model=model, max_tokens=max_tokens, messages=messages)
        if use_web_search:
            kwargs["tools"] = [{"type": "web_search_20260209", "name": "web_search"}]
        if system:
            kwargs["system"] = system

        # RateLimitError 발생 시 지수 백오프 재시도 (최대 3회)
        last_exc = None
        for attempt in range(3):
            try:
                response = self.client.messages.create(**kwargs)
                break
            except anthropic.RateLimitError as e:
                last_exc = e
                wait = 2 ** attempt * 5  # 5s, 10s, 20s
                logger.warning("Rate limit hit (attempt %d), retrying in %ds…", attempt + 1, wait)
                time.sleep(wait)
        else:
            raise last_exc

        text_content = " ".join(
            block.text for block in response.content if hasattr(block, "text")
        )
        result = {
            "role": "assistant",
            "content": text_content,
            "model": response.model,
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
        }

        # 캐시 저장
        if cache_key:
            _CACHE[cache_key] = {"result": result, "cached_at": time.time()}

        return result

    # ── 스트리밍 ─────────────────────────────────────────────────────────────────

    def stream(
        self,
        messages: list[dict],
        model: str = DEFAULT_MODEL,
        system: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ):
        """
        SSE 스트리밍용 제너레이터.
        각 청크의 텍스트를 yield 한다.

        사용 예:
            for chunk in anthropicServiceImpl.stream(messages):
                yield f"data: {chunk}\n\n"
        """
        kwargs = dict(model=model, max_tokens=max_tokens, messages=messages)
        if system:
            kwargs["system"] = system

        with self.client.messages.stream(**kwargs) as stream:
            for text in stream.text_stream:
                yield text
