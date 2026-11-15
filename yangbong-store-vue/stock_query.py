"""
한국 주식 종목코드(6자리) → 기업 개요 / 테마 / 뉴스 / 재무상태
Claude API 최소 token 쿼리 예제
"""

import anthropic
import json

# ── 시스템 프롬프트: 한 번만 정의, 짧게 유지 ─────────────────────────────
# 역할 + 출력 포맷을 함께 지정 → 불필요한 설명 토큰 차단
SYSTEM_PROMPT = """You are a Korean stock analyst. Given a 6-digit KRX stock code, return ONLY a JSON object with this exact schema — no explanation, no markdown:
{
  "company": {
    "name": "",        // 회사명
    "sector": "",      // 업종
    "overview": ""     // 2문장 이내 핵심 사업 요약
  },
  "themes": [""],      // 현재 관련 테마 (최대 5개, 키워드만)
  "news": [
    {"date": "", "headline": ""}  // 최근 주요 공시/뉴스 3건
  ],
  "financials": {
    "eps": null,
    "roe": null,
    "per": null,
    "pbr": null,
    "debt_ratio": null,  // 부채비율(%)
    "op_margin": null    // 영업이익률(%)
  },
  "data_note": ""        // 데이터 기준 시점 또는 불확실 항목 메모 (없으면 null)
}"""

# ── 유저 메시지: 종목코드만 전달 → 최소 토큰 ──────────────────────────────
def build_user_message(stock_code: str) -> str:
    return f"KRX:{stock_code}"


# ── API 호출 ──────────────────────────────────────────────────────────────
def query_stock(stock_code: str, api_key: str) -> dict:
    """
    종목코드 6자리를 받아 Claude API로 분석 결과 반환.

    token 절감 포인트:
    - system: 역할 + JSON 스키마를 한 번에 정의
    - user:   "KRX:005930" 같이 최소 문자열만 전달
    - max_tokens: JSON 응답에 충분한 512로 제한
    - model: claude-haiku-4-5 (가장 저렴, 구조화 출력에 적합)
    """
    client = anthropic.Anthropic(api_key=api_key)

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        system=SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": build_user_message(stock_code)}
        ]
    )

    raw = message.content[0].text.strip()

    # JSON 파싱
    result = json.loads(raw)

    # 토큰 사용량 출력 (참고용)
    usage = message.usage
    print(f"[token] input={usage.input_tokens}, output={usage.output_tokens}, "
          f"total={usage.input_tokens + usage.output_tokens}")

    return result


# ── 여러 종목 배치 처리 ──────────────────────────────────────────────────
def query_stocks_batch(stock_codes: list[str], api_key: str) -> dict[str, dict]:
    """
    여러 종목을 순차 처리. 추가 절감이 필요하면 한 번의 요청에
    여러 코드를 묶어 보낼 수 있으나 응답 품질이 낮아질 수 있음.
    """
    results = {}
    for code in stock_codes:
        print(f"\n▶ 조회 중: {code}")
        try:
            results[code] = query_stock(code, api_key)
        except json.JSONDecodeError as e:
            print(f"  JSON 파싱 실패: {e}")
            results[code] = {"error": "parse_error"}
        except anthropic.APIError as e:
            print(f"  API 오류: {e}")
            results[code] = {"error": str(e)}
    return results


# ── 실행 예시 ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import os

    API_KEY = os.environ.get("ANTHROPIC_API_KEY", "your-api-key-here")

    # 단일 종목
    code = "005930"  # 삼성전자
    data = query_stock(code, API_KEY)
    print(json.dumps(data, ensure_ascii=False, indent=2))

    # --- 출력 예시 ---
    # [token] input=~280, output=~210, total=~490
    # {
    #   "company": {
    #     "name": "삼성전자",
    #     "sector": "반도체/전자",
    #     "overview": "메모리·시스템반도체·스마트폰·가전을 주력으로 하는 글로벌 IT 기업."
    #   },
    #   "themes": ["AI반도체", "HBM", "스마트폰", "파운드리", "배당성장"],
    #   "news": [
    #     {"date": "2025-04", "headline": "HBM3E 엔비디아 공급 확대 협의"},
    #     {"date": "2025-03", "headline": "1분기 영업이익 컨센서스 상회"},
    #     {"date": "2025-02", "headline": "자사주 소각 계획 발표"}
    #   ],
    #   "financials": {
    #     "eps": 4316,
    #     "roe": 8.2,
    #     "per": 14.3,
    #     "pbr": 1.1,
    #     "debt_ratio": 28.4,
    #     "op_margin": 9.5
    #   },
    #   "data_note": "2024 연간 기준 추정치. 실시간 데이터 아님."
    # }
