STOCK_ANALYSIS_SYSTEM = (
    "한국 주식 애널리스트. 한국어, 마크다운, 개조식(불릿)으로 간결하게 답변."
)

_OVERVIEW_TEMPLATE = """\
종목코드 [{stock_code}] 분석. 각 항목 불릿 3~4개, 전체 800자 이내.

## 1. 기업 개요
회사명·업종·주요사업·시장지위

## 2. 재무 현황
분기별 매출·영업이익·순이익 추이, 부채비율, 주요 재무 이벤트
"""

_THEME_TEMPLATE = """\
종목코드 [{stock_code}] 분석. 불릿 3~4개, 400자 이내.

## 현재 테마
현재 연관 투자 테마(AI·2차전지·방산·바이오 등)
"""

_NEWS_TEMPLATE = """\
종목코드 [{stock_code}] 아래 최신 뉴스/공시 헤드라인을 참고해 요약. 불릿 3~4개, 400자 이내.
헤드라인에 없는 내용은 추측하지 말고, 관련 헤드라인이 없으면 "특이 공시·뉴스 없음"이라고 답변.

## 최근 공시 및 뉴스
{headlines}
"""


def build_overview_messages(stock_code: str) -> list[dict]:
    return [
        {
            "role": "user",
            "content": _OVERVIEW_TEMPLATE.format(stock_code=stock_code),
        }
    ]


def build_theme_messages(stock_code: str) -> list[dict]:
    return [
        {
            "role": "user",
            "content": _THEME_TEMPLATE.format(stock_code=stock_code),
        }
    ]


def build_news_messages(stock_code: str, headlines: list[dict]) -> list[dict]:
    if headlines:
        headline_text = "\n".join(
            f"- [{h['date']} {h['time']}] {h['title']} ({h['source']})"
            for h in headlines
        )
    else:
        headline_text = "(조회된 헤드라인 없음)"

    return [
        {
            "role": "user",
            "content": _NEWS_TEMPLATE.format(stock_code=stock_code, headlines=headline_text),
        }
    ]
