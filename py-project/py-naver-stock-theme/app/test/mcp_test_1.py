import json
from pprint import pprint

from app.ext_services.kis.KisEngine import KisEngine
from app.mcp_server import StockMcpServer
from app.services.stocks.StockModService import StockModService
from app.utils.constants.Literal import Literal

kis = KisEngine(virtual=False)

def get_stock_chart(stock_code: str, period: int = 200) -> str:
    ohlcv = kis.get_ohlcv_period(stock_code, period)
    if ohlcv is None:
        return json.dumps({"error": f"종목 {stock_code} 데이터를 찾을 수 없습니다."}, ensure_ascii=False)

    pprint(ohlcv)
    created = StockModService().createAddChannel(ohlcv).tail(200)
    created[Literal.YMD] = created[Literal.YMD].str[:10]
    records = created[[
        Literal.YMD, Literal.OPEN, Literal.HIGH, Literal.LOW, Literal.CLOSE, Literal.VOLUME,
        Literal.SMA_5, Literal.SMA_20, Literal.SMA_60, Literal.SMA_120,
        Literal.BB_UPPER, Literal.BB_MID, Literal.BB_LOWER,
    ]].to_dict(orient="records")
    return json.dumps(records, ensure_ascii=False, default=str)


def test():
    result = get_stock_chart(stock_code="SMR")
    pprint(result)