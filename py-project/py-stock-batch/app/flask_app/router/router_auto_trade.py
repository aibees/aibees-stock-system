"""
자동매매(AutoTrade) 화면 연동 — 매도 수기등록 전용 (2026-08-21).

stock-vue 의 `/api/v1/auto-trade/*` 는 원래 이 저장소에 없는 별도 백엔드(ROOT
서버, VITE_SERVER_URL)가 담당할 예정이었다(모드 설정·운용 상태·이력 등). 그중
"매도 수기등록"만은 이미 이 저장소(app/trade_worker)에 완전히 구현돼 있어서
(trade_worker_manual_sell, repository.py) ROOT 서버를 기다릴 이유가 없다 —
그래서 이 블루프린트만 먼저 이 앱(py-stock-batch)에 실제로 얹는다.
나머지 auto-trade 엔드포인트(모드/상태/이력)는 여전히 이 저장소 밖(ROOT)
소관이라 stock-vue 는 그쪽은 계속 USE_MOCK=true 로 둔다(useAutoTrade.js 참고).

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
from flask import Blueprint, request

from app.flask_app.utils.apiResponse import ApiResponse
from app.trade_worker.repository import Repository

auto_trade_bp = Blueprint("auto_trade", __name__)
_repo = Repository()


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


@auto_trade_bp.route("/manual-sell", methods=["GET"])
def get_manual_sell():
    """단일 슬롯 조회 — LimitOrder.vue 가 화면을 채울 때 부른다.
    종목코드를 모르는 상태에서 "지금 등록된 것"을 가져와야 하므로
    get_latest_manual_sell(enabled_flag 무관, state=ARMED 최신 1건)을 쓴다."""
    uid = _resolve_user_id()
    if uid is None:
        return ApiResponse.error("user_id 가 필요합니다.", status=400)
    try:
        row = _repo.get_latest_manual_sell(uid)
    except Exception as e:  # noqa: BLE001  (테이블 미생성 등)
        return ApiResponse.error(str(e), status=500)
    return ApiResponse.success(row)


@auto_trade_bp.route("/manual-sell", methods=["POST"])
def save_manual_sell():
    """등록/재등록(upsert). LimitOrder.vue 의 저장 버튼."""
    uid = _resolve_user_id()
    body = request.get_json(silent=True) or {}
    if uid is None:
        return ApiResponse.error("user_id 가 필요합니다.", status=400)
    code = body.get("stock_code")
    sell_price = body.get("sell_price")
    if not code:
        return ApiResponse.error("stock_code 가 필요합니다.", status=400)
    if sell_price is None or float(sell_price) <= 0:
        return ApiResponse.error("sell_price 가 필요합니다.", status=400)
    try:
        _repo.upsert_manual_sell(
            uid, code, body.get("stock_name"),
            sell_price, body.get("qty_ratio") or 1,
            body.get("memo"), body.get("enabled_flag") or "Y",
        )
        row = _repo.get_manual_sell(uid, code)
    except Exception as e:  # noqa: BLE001
        return ApiResponse.error(str(e), status=500)
    return ApiResponse.success(row)


@auto_trade_bp.route("/manual-sell/cancel", methods=["POST"])
def cancel_manual_sell():
    """사용자 취소. LimitOrder.vue 의 취소 버튼은 stock_code 를 안 실어보내므로
    (단일 슬롯 화면) body 에 없으면 현재 ARMED 인 종목을 찾아 취소한다."""
    uid = _resolve_user_id()
    if uid is None:
        return ApiResponse.error("user_id 가 필요합니다.", status=400)
    body = request.get_json(silent=True) or {}
    code = body.get("stock_code")
    try:
        if not code:
            current = _repo.get_latest_manual_sell(uid)
            code = current["stock_code"] if current else None
        if code:
            _repo.cancel_manual_sell(uid, code)
    except Exception as e:  # noqa: BLE001
        return ApiResponse.error(str(e), status=500)
    return ApiResponse.success(None)
