STOCK_ANALYSIS_SYSTEM = (
    "한국 주식 전문 애널리스트. 반드시 한국어로 답변. 요청한 4개 섹션 형식 준수."
)

_USER_TEMPLATE = """\
종목코드 [{stock_code}] 분석. 마크다운, 2000자 이내.
웹 검색을 통한 최신 정보 도출 요망.
## 1. 기업 개요
회사명·업종·주요사업·시장지위

## 2. 현재 테마
현재 연관 투자 테마(AI·2차전지·방산·바이오 등)

## 3. 재무 현황
분기별 매출·영업이익·순이익 추이, 부채비율, 주요 재무 이벤트

## 4. 최근 공시 및 뉴스
최근 공시·퀀트 신호 요약
"""


def build_stock_analysis_messages(stock_code: str) -> list[dict]:
    return [
        {
            "role": "user",
            "content": _USER_TEMPLATE.format(stock_code=stock_code),
        }
    ]
