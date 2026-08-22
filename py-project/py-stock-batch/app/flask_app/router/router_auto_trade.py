"""
자동매매(AutoTrade) 화면 연동 — 매도 수기등록 전용 (2026-08-20, 2026-08-21 다건화).

stock-vue 의 `/api/v1/auto-trade/*` 는 원래 이 저장소에 없는 별도 백엔드(ROOT
서버, VITE_SERVER_URL)가 담당할 예정이었다(모드 설정·운용 상태·이력 등). 그중
"매도 수기등록"만은 이미 이 저장소(app/trade_worker)에 완전히 구현돼 있어서
(trade_worker_manual_sell, repository.py) ROOT 서버를 기다릴 이유가 없다 —
그래서 이 블루프린트만 먼저 이 앱(py-stock-batch)에 실제로 얹는다.
나머지 auto-trade 엔드포인트(모드/상태/이력)는 여전히 이 저장소 밖(ROOT)
소관이라 stock-vue 는 그쪽은 계속 USE_MOCK=true 로 둔다(useAutoTrade.js 참고).

2026-08-21 변경 2가지:
  1) 등록 가능 조건을 "worker 가 직접 매수해 trade_worker_position 에 있는 종목"
     에서 "계좌 실보유(user_holdings)에 있는 종목"으로 넓혔다 — HTS/MTS 로 직접
     산 종목도 worker 가 편입(wallet_sync 주기 폴링)하기 전에 바로 등록할 수 있다.
     실시간 감시 시작은 여전히 wallet_sync.reconcile_wallet 편입에 달려 있다
     (등록 자체를 막지는 않는다 — sell_executor.reload_manual_sells 참고).
  2) 종목당 1건(유저+종목 upsert)이었던 제약을 풀어 종목당 여러 지정가(사다리
     매도)와 여러 종목 동시 등록을 허용했다(sql/09_manual_sell_multi_ddl.sql).
     그래서 GET 은 이제 "지금 등록된 것 1건"이 아니라 유저의 등록 전체 목록을,
     POST 는 upsert 가 아니라 매번 새 티어 생성을, cancel 은 stock_code 대신
     manual_sell_id 로 특정 티어 하나만 취소한다.

인증 관련 주의:
  이 Flask 앱(runner.py)에는 JWT 디코드/사용자 식별 미들웨어가 전혀 없다
  (job_bp 를 포함해 기존 라우트 전부 무인증) — ROOT 서버 전용 인증 체계를
  여기서 새로 구현하지 않았다. 그래서 user_id 는 프런트가 로그인 세션에서
  직접 실어보낸다(useAutoTrade.js 의 currentUserId()). 즉 이 엔드포인트는
  이 앱의 기존 보안 수준(무인증 내부망 batch-admin 서비스)을 그대로 따른다 —
  더 강한 인증이 필요하면 이 앱 전체의 인증 체계부터 새로 설계해야 한다.

CORS 주의:
  runner.py 의 CORS 설정이 methods=['GET','POST','OPTIONS'] 뿐이라(PUT/DELETE
  없음) 여기서는 저장/취소도 모두 POST 로 받는다(REST 정석은 PUT/DELETE 지만
  이 앱 전체 CORS 설정을 건드리지 않기 위한 선택).
"""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from flask import Blueprint, request

from app.flask_app.utils.apiResponse import ApiResponse
from app.trade_worker.repository import Repository

auto_trade_bp = Blueprint("auto_trade", __name__)
_repo = Repository()


def _jsonable(obj):
    """ApiResponse.success 가 json.dumps 를 인코더 지정 없이 그대로 쓰기 때문에
    (app/flask_app/utils/apiResponse.py), DB 에서 그대로 나온 row(dict)를 넘기면
    Decimal(sell_price/qty_ratio/base_qty/qty 등)·datetime(created_at 등) 필드에서
    'Object of type Decimal is not JSON serializable' 로 500 이 난다. 라우트가
    반환하는 row/list 는 이 함수로 한 번 정리해서 넘긴다."""
    if obj is None:
        return None
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    return obj


def _resolve_user_id():
    """query string 또는 JSON body 의 user_id. 없거나 정수가 아니면 None."""
    raw = request.args.get("user_id")
    if raw is None:
        body = request.get_json(silent=True) or {}
        raw = body.get("user_id")
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


@auto_trade_bp.route("/holdings", methods=["GET"])
def get_holdings():
    """계좌 실보유(user_holdings) 목록 — LimitOrder.vue 의 "종목 선택"이 이 목록에서
    고르게 한다. worker 가 직접 매수한 것(trade_worker_position)으로 좁히지 않는다 —
    HTS/MTS 로 직접 산 종목도 계좌에 있으면(user_holdings) 그대로 노출한다."""
    uid = _resolve_user_id()
    if uid is None:
        return ApiResponse.error("user_id 가 필요합니다.", status=400)
    try:
        rows = _repo.get_user_holdings(uid)
    except Exception as e:  # noqa: BLE001
        return ApiResponse.error(str(e), status=500)
    return ApiResponse.success(_jsonable(rows))


@auto_trade_bp.route("/manual-sell", methods=["GET"])
def get_manual_sell():
    """수기등록 전체 목록 조회 — LimitOrder.vue 가 화면을 채울 때 부른다.
    2026-08-21 다건화 이후로는 "지금 등록된 것 1건"이 아니라 유저의 등록 전체
    (모든 상태 포함, 종목코드 → 지정가 오름차순)를 반환한다. 화면은 이를
    종목별로 묶어 티어 리스트로 보여준다."""
    uid = _resolve_user_id()
    if uid is None:
        return ApiResponse.error("user_id 가 필요합니다.", status=400)
    try:
        rows = _repo.get_manual_sells(uid)
    except Exception as e:  # noqa: BLE001  (테이블 미생성 등)
        return ApiResponse.error(str(e), status=500)
    return ApiResponse.success(_jsonable(rows))


@auto_trade_bp.route("/manual-sell", methods=["POST"])
def save_manual_sell():
    """신규 티어 등록. LimitOrder.vue 의 저장 버튼 — 같은 종목이라도 항상 새 행을
    만든다(종목당 여러 지정가 허용). 등록 가능 조건은 계좌 실보유(user_holdings)
    뿐이다 — worker 가 그 종목을 직접 산 게 아니어도(HTS/MTS 매수분 포함) 등록할
    수 있다. 실시간 감시 시작(구독)은 wallet_sync.reconcile_wallet 의 다음 폴링
    (기본 30초)에 달려 있다는 점은 화면 안내 문구로 알린다."""
    uid = _resolve_user_id()
    body = request.get_json(silent=True) or {}
    if uid is None:
        return ApiResponse.error("user_id 가 필요합니다.", status=400)
    code = body.get("stock_code")
    sell_price = body.get("sell_price")
    if not code:
        return ApiResponse.error("stock_code 가 필요합니다.", status=400)
    try:
        sell_price_dec = Decimal(str(sell_price))
    except (InvalidOperation, TypeError, ValueError):
        sell_price_dec = None
    if sell_price_dec is None or sell_price_dec <= 0:
        return ApiResponse.error("sell_price 가 필요합니다.", status=400)

    try:
        holding = _repo.get_user_holding(uid, code)
    except Exception as e:  # noqa: BLE001
        return ApiResponse.error(str(e), status=500)
    if not holding or Decimal(str(holding.get("qty") or 0)) <= 0:
        return ApiResponse.error(
            "계좌에 보유 중인 종목이 아닙니다(user_holdings 기준). "
            "직접 매수한 종목이 아니어도 계좌에 있으면 등록할 수 있지만, "
            "지금 보유 수량이 없는 종목은 등록할 수 없습니다.", status=400)
    base_qty = Decimal(str(holding["qty"]))

    try:
        new_id = _repo.insert_manual_sell(
            uid, code, body.get("stock_name") or holding.get("stock_name"),
            sell_price_dec, body.get("qty_ratio") or 1,
            body.get("memo"), body.get("enabled_flag") or "Y",
            base_qty=base_qty,
        )
        row = _repo.get_manual_sell_by_id(uid, new_id)
    except Exception as e:  # noqa: BLE001
        return ApiResponse.error(str(e), status=500)
    return ApiResponse.success(_jsonable(row))


@auto_trade_bp.route("/manual-sell/cancel", methods=["POST"])
def cancel_manual_sell():
    """사용자 취소 — 종목당 여러 티어가 있을 수 있으므로 반드시 manual_sell_id 로
    특정 행 하나만 취소한다(같은 종목의 다른 티어는 건드리지 않는다)."""
    uid = _resolve_user_id()
    if uid is None:
        return ApiResponse.error("user_id 가 필요합니다.", status=400)
    body = request.get_json(silent=True) or {}
    manual_sell_id = body.get("manual_sell_id") or body.get("id")
    if manual_sell_id is None:
        return ApiResponse.error("manual_sell_id 가 필요합니다.", status=400)
    try:
        _repo.cancel_manual_sell(uid, int(manual_sell_id))
    except (TypeError, ValueError):
        return ApiResponse.error("manual_sell_id 가 올바르지 않습니다.", status=400)
    except Exception as e:  # noqa: BLE001
        return ApiResponse.error(str(e), status=500)
    return ApiResponse.success(None)
