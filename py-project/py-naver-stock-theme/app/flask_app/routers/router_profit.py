"""
사용자별 매매손익 조회 — KIS 기간별매매손익현황조회(TTTC8715R) 중계.

화면: stock-vue/src/components/Trade/TradeProfit.vue (/trade/profit)
KIS: /uapi/domestic-stock/v1/trading/inquire-period-trade-profit
     = HTS[0856] 기간별 매매손익 > "종목별". 실전 전용(모의투자 미지원).

MyWallet(계좌 현황)과 보는 숫자가 다르다 — 거긴 지금 **보유 중**인 종목의
평가손익이고, 여기는 **매도로 확정된** 실현손익이다. 그래서 둘을 더해도
'총수익'이 되지 않는다(화면에도 안내 문구를 둔다).

DB 에 적재하지 않고 매 요청마다 KIS 를 직접 호출한다 — 실현손익은 KIS 가
확정해 주는 값이고, 수수료·제세금까지 포함해 우리가 재계산하면 HTS 화면과
어긋나기 때문이다. 대신 KisEngine(PyKis 세션)은 유저별로 캐시한다(아래 주석).

인증 (router_account_trade.py 와 동일 규칙):
  이 앱은 @require_auth 로 JWT 를 검증하고 g.current_user_id 를 채운다.
  조회 대상 user_id 는 **JWT 에서만** 가져온다 — query string 의 user_id 를
  신뢰하면 남의 계좌 실현손익을 그대로 읽을 수 있다. 호환을 위해 user_id
  파라미터를 받기는 하지만 JWT 와 다르면 403 으로 거절한다.
  (이 파일은 원래 py-stock-batch 에 있었다. 그쪽은 인증 미들웨어가 없는
   내부망 서비스라 프런트가 보낸 user_id 를 그대로 썼는데, 이 앱으로 옮기면서
   그 전제가 더 이상 맞지 않으므로 JWT 기준으로 바꿨다.)
"""
import logging
from datetime import date, datetime, timedelta

from flask import Blueprint, request, g

from app.ext_services.kis.KisEngine import KisEngine
from app.flask_app.routers.router_oauth import require_auth
from app.flask_app.utils.apiResponse import ApiResponse

log = logging.getLogger("flask.profit")
log.setLevel(logging.INFO)

profit_bp = Blueprint("profit", __name__)

# 조회 기간 상한(일). KIS 가 문서상 제한을 명시하진 않지만, 기간이 길면 연속조회가
# 수십 페이지로 늘어나 요청 하나가 Flask 워커를 오래 점유한다. 화면 기본값은 1개월.
MAX_RANGE_DAYS = 366
# 기간 미지정 시 기본 조회 구간(최근 N일).
DEFAULT_RANGE_DAYS = 30

def _get_engine(user_id: int) -> KisEngine:
    """이 유저 계정의 KIS 세션.

    virtual=False 가 필수다 — 이 API(TTTC8715R)는 모의투자 미지원이고,
    KisEngine 의 virtual 기본값은 True 라 생략하면 모의 세션이 잡힌다.

    인스턴스 캐시는 KisEngine 이 (virtual, user_id) 싱글톤으로 이미 갖고 있어
    여기서 따로 캐시하지 않는다. PyKis 생성은 토큰 준비를 수반하고 발급은 KIS 가
    1분 1회로 제한(EGW00133)하므로, 계정당 1개 재사용이 중요하다.
    """
    return KisEngine(virtual=False, user_id=user_id)


def _parse_ymd(raw, default: date) -> date | None:
    """'YYYY-MM-DD' / 'YYYYMMDD' 모두 허용. 빈값이면 default, 형식오류면 None."""
    if raw is None or str(raw).strip() == "":
        return default
    s = str(raw).strip().replace("-", "").replace(".", "").replace("/", "")
    try:
        return datetime.strptime(s, "%Y%m%d").date()
    except ValueError:
        return None


def _num(v, default=0.0) -> float:
    """KIS 응답은 숫자도 전부 문자열로 온다. 빈 문자열/None 도 섞여 있다."""
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return default


def _code(pdno) -> str:
    """상품번호 → 종목코드. KIS 문서상 pdno 는 길이 12 이고 '종목번호(뒤 6자리만
    해당)' 라고 명시돼 있어, 6자리를 넘겨 오면 뒤 6자리만 쓴다(앞자리는 패딩)."""
    s = str(pdno or "").strip()
    if len(s) > 6 and s[-6:].isdigit():
        return s[-6:]
    return s


def _row(r: dict) -> dict:
    """KIS output1 1행 → 화면용 필드. 금액/수량은 숫자로 바꿔 넘긴다
    (프런트에서 문자열 '0' 과 0 을 구분하느라 헤매지 않도록)."""
    trad_dt = str(r.get("trad_dt") or "").strip()
    return {
        # 'YYYYMMDD' → 'YYYY-MM-DD'. 파싱 불가하면 원문 유지.
        "trade_date": (f"{trad_dt[:4]}-{trad_dt[4:6]}-{trad_dt[6:8]}"
                       if len(trad_dt) == 8 and trad_dt.isdigit() else trad_dt),
        "stock_code": _code(r.get("pdno")),
        "stock_name": (r.get("prdt_name") or "").strip(),
        "trade_type": (r.get("trad_dvsn_name") or "").strip(),
        "hold_qty": _num(r.get("hldg_qty")),
        "buy_qty": _num(r.get("buy_qty")),
        "buy_price": _num(r.get("pchs_unpr")),
        "buy_amount": _num(r.get("buy_amt")),
        "sell_qty": _num(r.get("sll_qty")),
        "sell_price": _num(r.get("sll_pric")),
        "sell_amount": _num(r.get("sll_amt")),
        # rlzt_pfls = 실현손익(수수료·제세금 차감 후). 우리가 매도금액-매수금액으로
        # 재계산하지 않는 이유는 모듈 docstring 참고.
        "realized_profit": _num(r.get("rlzt_pfls")),
        "profit_rate": _num(r.get("pfls_rt")),
        "fee": _num(r.get("fee")),
        "tax": _num(r.get("tl_tax")),
        "loan_interest": _num(r.get("loan_int")),
    }


def _summary(o: dict) -> dict:
    """KIS output2(합계) → 화면용 필드. 합계는 KIS 가 준 값을 그대로 쓴다 —
    행을 더해서 만들면 연속조회 상한에 걸려 일부만 받은 경우 숫자가 틀린다."""
    return {
        "sell_qty": _num(o.get("sll_qty_smtl")),
        "sell_amount": _num(o.get("sll_tr_amt_smtl")),
        "sell_fee": _num(o.get("sll_fee_smtl")),
        "sell_tax": _num(o.get("sll_tltx_smtl")),
        "sell_settle_amount": _num(o.get("sll_excc_amt_smtl")),
        "buy_qty": _num(o.get("buyqty_smtl")),
        "buy_amount": _num(o.get("buy_tr_amt_smtl")),
        "buy_fee": _num(o.get("buy_fee_smtl")),
        "buy_tax": _num(o.get("buy_tax_smtl")),
        "buy_settle_amount": _num(o.get("buy_excc_amt_smtl")),
        "total_qty": _num(o.get("tot_qty")),
        "total_amount": _num(o.get("tot_tr_amt")),
        "total_fee": _num(o.get("tot_fee")),
        "total_tax": _num(o.get("tot_tltx")),
        "total_settle_amount": _num(o.get("tot_excc_amt")),
        "total_realized_profit": _num(o.get("tot_rlzt_pfls")),
        "total_profit_rate": _num(o.get("tot_pftrt")),
        "loan_interest": _num(o.get("loan_int")),
    }


@profit_bp.route("/trade-profit", methods=["GET"])
@require_auth
def get_trade_profit():
    """기간별 매매손익(실현손익) 조회. 조회 대상은 로그인한 본인 계좌다.

    query: start, end('YYYY-MM-DD'|'YYYYMMDD', 생략 시 최근 30일),
           stock_code(선택, 특정 종목만), sort('00' 최근순 기본 | '01' 과거순),
           user_id(선택 — JWT 와 일치해야 하며 불일치 시 403)
    """
    # 대상 유저는 JWT 에서만 결정한다(모듈 docstring 참고).
    user_id = int(g.current_user_id)
    raw_uid = request.args.get("user_id")
    if raw_uid not in (None, ""):
        try:
            if int(raw_uid) != user_id:
                return ApiResponse.error("본인 계좌만 조회할 수 있습니다.", status=403)
        except (TypeError, ValueError):
            return ApiResponse.error("user_id 가 올바르지 않습니다.", status=400)

    today = date.today()
    end = _parse_ymd(request.args.get("end"), today)
    start = _parse_ymd(request.args.get("start"), today - timedelta(days=DEFAULT_RANGE_DAYS))
    if start is None or end is None:
        return ApiResponse.error("start/end 형식이 올바르지 않습니다. (YYYY-MM-DD)", status=400)
    if start > end:
        start, end = end, start
    if (end - start).days > MAX_RANGE_DAYS:
        return ApiResponse.error(
            f"조회 기간은 최대 {MAX_RANGE_DAYS}일까지 가능합니다.", status=400)

    sort_dvsn = request.args.get("sort") or "00"
    if sort_dvsn not in ("00", "01", "02"):
        sort_dvsn = "00"

    # 키 미등록/계좌번호 형식 오류는 stock_shared.kis.credentials.load_creds_from_db 가
    # KisCredentialError(= ValueError 하위) 로 올린다. 이 앱에는 py-stock-batch 같은 kis.key 파일 fallback 이 없어서
    # "키 없는 유저가 다른 계좌를 보게 되는" 경로는 애초에 없다 — 그대로 거절한다.
    try:
        engine = _get_engine(user_id)
    except ValueError as e:
        log.info("KIS 인증정보 없음(user_id=%s): %s", user_id, e)
        return ApiResponse.error(
            "등록된 KIS 계정이 없습니다. 사용자 설정에서 KIS 키를 먼저 등록해 주세요.",
            status=400)
    except Exception as e:  # noqa: BLE001
        log.warning("KisEngine 생성 실패(user_id=%s): %s", user_id, e)
        return ApiResponse.error(f"KIS 세션 생성에 실패했습니다: {e}", status=500)

    try:
        result = engine.get_period_trade_profit(
            start.strftime("%Y%m%d"), end.strftime("%Y%m%d"),
            symbol=(request.args.get("stock_code") or "").strip() or None,
            sort_dvsn=sort_dvsn,
        )
    except Exception as e:  # noqa: BLE001
        log.warning("매매손익 조회 실패(user_id=%s): %s", user_id, e)
        return ApiResponse.error(f"매매손익 조회에 실패했습니다: {e}", status=500)

    if result is None:
        return ApiResponse.error(
            "KIS 매매손익 조회에 실패했습니다. 잠시 후 다시 시도해 주세요.", status=502)

    return ApiResponse.success({
        "start": start.isoformat(),
        "end": end.isoformat(),
        "rows": [_row(r) for r in result["rows"]],
        "summary": _summary(result["summary"] or {}),
        # 연속조회 상한에 걸려 일부만 받았으면 화면이 "일부만 표시" 를 알린다.
        "truncated": bool(result.get("truncated")),
    })
