"""
MCP Server — Streamable HTTP + Bearer Auth

실행:  python -m app.main mcp
환경변수:
    MCP_HOST           바인딩 주소       (default: 0.0.0.0)
    MCP_PORT           포트              (default: 8001)
    MCP_CLIENT_SECRET  Bearer 토큰 값
"""
from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime
from typing import Optional

from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount



from app.config.db.database import dbConn
from app.domains.dao.masterStockDao import MasterStockDao
from app.domains.dao.tradeBuyTargetStockDao import TradeBuyTargetStockDao
from app.ext_services.kis.KisEngine import KisEngine
from app.ext_services.yf.yfEngine import yfEngine
from app.services.stocks.StockModService import StockModService
from app.utils.constants.Literal import Literal

# ────────────────────────────────────────────────────────────
# 설정
# ────────────────────────────────────────────────────────────
_MCP_PORT = int(os.getenv("MCP_PORT", "5558"))
_BEARER_TOKEN = os.getenv("MCP_CLIENT_SECRET", "")


# ════════════════════════════════════════════════════════════
# BearerAuthMiddleware
# ════════════════════════════════════════════════════════════
class BearerAuthMiddleware(BaseHTTPMiddleware):
    """
    Authorization: Bearer <MCP_CLIENT_SECRET> 헤더 검증 미들웨어.
    OPTIONS → 통과, 그 외 토큰 불일치 → 401.
    """

    async def dispatch(self, request: Request, call_next):
        if request.method == "OPTIONS":
            return await call_next(request)

        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return self._unauthorized("Bearer token required")

        if auth[7:] != _BEARER_TOKEN:
            return self._unauthorized("Invalid token")

        return await call_next(request)

    @staticmethod
    def _unauthorized(detail: str) -> JSONResponse:
        return JSONResponse(
            {"error": "unauthorized", "detail": detail},
            status_code=401,
            headers={"WWW-Authenticate": "Bearer"},
        )


# ════════════════════════════════════════════════════════════
# StockMcpServer
# ════════════════════════════════════════════════════════════
class StockMcpServer:
    """
    주식 도메인 MCP 서버.
    - tool 등록 : _register_tools()
    - ASGI 앱 생성 : build_asgi_app()
    """

    def __init__(self):
        self._mcp = FastMCP("naver-stock-theme", stateless_http=True, host="0.0.0.0")
        self._register_tools()

    # ── 내부 헬퍼 ───────────────────────────────────────────

    @staticmethod
    @contextmanager
    def _db():
        """Flask g 없이 DB 세션을 직접 관리합니다."""
        session = dbConn.get_session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.remove()

    @staticmethod
    def _kis(virtual: bool = False) -> KisEngine:
        return KisEngine(virtual=virtual)

    @staticmethod
    def _yf() -> yfEngine:
        return yfEngine()

    @staticmethod
    def _is_us(code: str) -> bool:
        """6자리 숫자 → KR, 그 외 → US"""
        return not (len(code) == 6 and code.isdigit())

    # ── Tool 등록 ────────────────────────────────────────────

    def _register_tools(self):
        mcp = self._mcp

        @mcp.tool(
            name="search_stocks",
            description=(
                "종목명 또는 종목코드로 국내 주식 종목을 검색합니다. "
                "include_code=True 로 설정하면 종목코드도 검색 대상에 포함됩니다. "
                "반환값: [{stock_code, stock_name, ...}] JSON 배열."
            ),
        )
        def search_stocks(stock_name: str, include_code: bool = False) -> str:
            dao = MasterStockDao()
            with self._db() as session:
                results = dao.select_master_stock(session, {
                    "stock_name": stock_name,
                    "search_option": include_code,
                })
                return json.dumps(
                    [r.to_dict() if hasattr(r, "to_dict") else str(r) for r in results],
                    ensure_ascii=False,
                )

        @mcp.tool(
            name="get_stock_chart",
            description=(
                "종목의 OHLCV 캔들 데이터와 기술적 지표(SMA 5/20/60/120, 볼린저밴드, MACD, OBV, RSI)를 "
                "조회합니다. 국내 종목(6자리 숫자)은 KIS, 미국 종목(영문 티커)은 yFinance를 사용합니다. "
                "period: int. 가져올 캔들 개수(근사). 0 ~ 200. "
                "unit: 봉 단위. 'day'(기본) | 'week' | 'month' | 'year'. "
                "반환값: [{ymd, open, high, low, close, volume, sma5, sma20, sma60, sma120, "
                "bb_upper, bb_mid, bb_lower, macd, macd_signal, obv, obv_signal, rsi, rsi_signal}] JSON 배열."
            ),
        )
        def get_stock_chart(stock_code: str, period: int = 200, unit: str = "day") -> str:
            if self._is_us(stock_code):
                ohlcv = self._yf().get_ohlcv_period_unit(stock_code, period, unit)
            else:
                ohlcv = self._kis().get_ohlcv_period_unit(stock_code, period, unit)

            if ohlcv is None:
                return json.dumps({"error": f"종목 {stock_code} 데이터를 찾을 수 없습니다."}, ensure_ascii=False)

            created = StockModService().createAddChannel(ohlcv).tail(200)
            created[Literal.YMD] = created[Literal.YMD].str[:10]
            records = created[[
                Literal.YMD, Literal.OPEN, Literal.HIGH, Literal.LOW, Literal.CLOSE, Literal.VOLUME,
                Literal.SMA_5, Literal.SMA_20, Literal.SMA_60, Literal.SMA_120,
                Literal.BB_UPPER, Literal.BB_MID, Literal.BB_LOWER,
                Literal.MACD, Literal.MACD_SIGNAL,
                Literal.OBV, Literal.OBV_SIGNAL,
                Literal.RSI, Literal.RSI_SIGNAL,
            ]].to_dict(orient="records")
            return json.dumps(records, ensure_ascii=False, default=str)

        @mcp.tool(
            name="get_stock_ohlcv",
            description=(
                "날짜 범위를 지정해 종목의 일별 OHLCV(시가·고가·저가·종가·거래량) 데이터를 조회합니다. "
                "start_date/end_date 형식: 'YYYY-MM-DD'. end_date 생략 시 오늘 기준. "
                "반환값: [{ymd, open, high, low, close, volume}] JSON 배열."
            ),
        )
        def get_stock_ohlcv(
            stock_code: str,
            start_date: str,
            end_date: Optional[str] = None,
        ) -> str:
            end = end_date or datetime.today().strftime("%Y-%m-%d")
            if self._is_us(stock_code):
                ohlcv = self._yf().get_ohlcv(stock_code, start_date, end)
            else:
                ohlcv = self._kis().getOHLCV(stock_code, start_date, end)
            if ohlcv is None:
                return json.dumps({"error": f"종목 {stock_code} 데이터를 찾을 수 없습니다."}, ensure_ascii=False)
            return ohlcv.to_json(orient="records", force_ascii=False)

        @mcp.tool(
            name="get_stock_finance_info",
            description=(
                "종목의 주요 재무 투자 지표를 조회합니다. "
                "반환값: {eps(주당순이익), per(주가수익비율), pbr(주가순자산비율), "
                "roe(자기자본이익률, pbr/per), peg(PEG비율, per/eps)} JSON 객체. "
                "고평가·저평가 판단이나 종목 비교에 활용하세요."
            ),
        )
        def get_stock_finance_info(stock_code: str) -> str:
            return json.dumps(self._kis().get_finance_info(stock_code), ensure_ascii=False)

        @mcp.tool(
            name="get_buy_target_stocks",
            description=(
                "특정 날짜의 매수 추천 종목 목록을 조회합니다. "
                "ymd 형식: 'YYYYMMDD' (예: '20260612'). 생략 시 오늘 날짜 기준. "
                "반환값: [{stock_code, stock_name, close, ...}] JSON 배열."
            ),
        )
        def get_buy_target_stocks(ymd: Optional[str] = None) -> str:
            date_str = ymd or datetime.today().strftime("%Y%m%d")
            with self._db() as session:
                results = TradeBuyTargetStockDao().select_trade_buy_target_daily(
                    session, {Literal.YMD: date_str}
                )
                return json.dumps(results, ensure_ascii=False, default=str)

        @mcp.tool(
            name="get_stock_recent_record",
            description=(
                "종목의 최근 매수 추천 시점 대비 현재까지의 수익률 현황을 조회합니다. "
                "반환값: {rec_record, max_record, now_record} — 각각 {ymd, close, rate}. "
                "rec=추천 당시 종가, max=추천 이후 최고가, now=현재가. rate는 등락률(%)."
            ),
        )
        def get_stock_recent_record(stock_code: str) -> str:
            from app.services.stocks.StockService import StockService
            with self._db() as session:
                result = StockService().get_target_rec_record(
                    session, {Literal.STOCK_CODE: stock_code}
                )
                return json.dumps(result, ensure_ascii=False, default=str)

    # ── ASGI 앱 빌드 ─────────────────────────────────────────

    def build_asgi_app(self) -> Starlette:
        """
        OAuth 라우트 + MCP 라우트를 하나의 Starlette 앱으로 조립합니다.

        [주의] Starlette은 Mount된 서브앱의 lifespan을 자동 호출하지 않습니다.
        FastMCP의 task group 초기화가 누락되면 "Task group is not initialized" 에러가
        발생하므로, 외부 앱 lifespan에서 mcp_asgi의 lifespan을 직접 위임합니다.
        """
        mcp_asgi = self._mcp.streamable_http_app()

        @asynccontextmanager
        async def lifespan(app: Starlette):
            async with mcp_asgi.router.lifespan_context(mcp_asgi):
                yield

        app = Starlette(
            lifespan=lifespan,
            routes=[
                Mount("/", app=mcp_asgi),
            ],
        )
        app.add_middleware(BearerAuthMiddleware)
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
        )
        return app


# ────────────────────────────────────────────────────────────
# 공개 팩토리 (main.py / mcp_server 직접 실행 시 호출)
# ────────────────────────────────────────────────────────────
def create_app() -> Starlette:
    return StockMcpServer().build_asgi_app()

