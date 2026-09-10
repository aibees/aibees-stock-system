import logging
import time
import anthropic
from app.config.anthropicConfig import anthropic_settings

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-sonnet-5"
DEFAULT_MAX_TOKENS = 8096
# 재시도할 가치가 있는(=우리 쪽 재요청으로 나아질 수 있는) 일시적 오류만 재시도한다.
# 429 레이트리밋, 529 과부하, 500/502/503/504 서버 오류.
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504, 529}

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
            # max_uses=1: 검색 1회당 $0.01 과금 외에도 검색결과 자체가 input 토큰으로 크게 붙는다
            # (실측: 검색 3회 = input 약 79,000토큰, 요청당 약 $0.26 — 검색 미사용 대비 약 37배).
            # 최신 공시 1건 확인이 목적이므로 1회로 제한해 비용을 억제한다.
            kwargs["tools"] = [{"type": "web_search_20260209", "name": "web_search", "max_uses": 1}]
        if system:
            kwargs["system"] = system

        # 일시적 오류(레이트리밋 429, 서버 과부하 529, 5xx, 연결 오류) 지수 백오프 재시도 (최대 3회)
        # 429만 잡던 예전 코드는 Anthropic 서버가 잠깐 과부하(529)일 때 재시도 없이 바로
        # 에러를 사용자에게 노출시켜 "input/output limit over" 로 보이는 원인이 됐다.
        # 400/401/403/404 등 재시도해도 똑같이 실패할 오류는 즉시 전파한다.
        last_exc = None
        for attempt in range(3):
            try:
                response = self.client.messages.create(**kwargs)
                break
            except (anthropic.APIStatusError, anthropic.APIConnectionError) as e:
                status = getattr(e, "status_code", None)
                if isinstance(e, anthropic.APIStatusError) and status not in RETRYABLE_STATUS_CODES:
                    raise
                last_exc = e
                wait = 2 ** attempt * 5  # 5s, 10s, 20s
                logger.warning(
                    "일시적 오류(status=%s, attempt %d/3), %ds 후 재시도: %s",
                    status, attempt + 1, wait, e,
                )
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
