"""
router_account_trade.py — 계좌 현황 / 거래 내역 조회 라우터 (READ-ONLY)

명세: "계좌 현황 · 거래 내역 — BE(Flask) 협조요청 명세서"
프론트: MyWallet.vue(계좌 현황), TradeLog.vue(거래 내역)

엔드포인트 (Blueprint url_prefix = /api/v1/users):
    GET /<userId>/account             ① 계좌 요약        (단건 객체)
    GET /<userId>/portfolio           ② 보유 포트폴리오  (holdings + summary)
    GET /<userId>/positions           ③ worker 포지션    (목록 래퍼)
    GET /<userId>/positions/history   ④ worker 매매 이력 (목록 래퍼)
    GET /<userId>/trade-logs          ⑤ 거래(체결) 로그  (목록 래퍼)
    GET /<userId>/worker-logs         ⑥ 운영 로그        (목록 래퍼)

명세 준수 사항:
    - 응답 envelope 은 이 화면 전용 계약을 따른다(ApiResponse 미사용).
        · 목록: { "data": [...], "page": {limit, offset, total} }
        · 단건: 래퍼 없이 객체 그대로 / holdings+summary
        · 오류: { "error": { "code": "...", "message": "..." } } + HTTP status
    - DECIMAL 은 문자열, datetime 은 ISO8601 로 직렬화 (_row).
    - user_id 스코프 강제: 경로 userId 와 JWT user_id(g.current_user_id) 일치 검증,
      불일치 시 403 FORBIDDEN.
    - 인증은 기존 @require_auth 재사용(실패 시 401).
"""

import logging
from decimal import Decimal

from flask import Blueprint, request, g, Response
import simplejson as json

from app.domains.dao.accountTradeDao import AccountTradeDao
from app.flask_app.routers.router_oauth import require_auth

logging.basicConfig(level=logging.ERROR)

account_trade_bp = Blueprint("account_trade", __name__)

accountTradeDaoImpl = AccountTradeDao()

MAX_LIMIT = 200  # 페이지 크기 상한


# ===============================================================================
# 직렬화 / 응답 헬퍼
# ===============================================================================
def _row(d: dict) -> dict:
    """DB row → JSON-safe dict. DECIMAL → str(지수표기 방지), datetime → ISO8601(초)."""
    out = {}
    for k, v in d.items():
        if isinstance(v, Decimal):
            out[k] = format(v, "f")
        elif hasattr(v, "isoformat"):
            out[k] = v.isoformat(timespec="seconds")
        else:
            out[k] = v
    return out


def _json(body: dict, status: int = 200) -> Response:
    # 직렬화는 ApiResponse._dumps 로 통일 (datetime 등 공통 default 적용).
    # 위 _serialize 가 대부분 미리 변환하지만, 거기 안 걸린 중첩 구조가
    # 남아 있어도 여기서 안전하게 처리된다.
    from app.flask_app.utils.apiResponse import _dumps
    return Response(
        _dumps(body),
        status=status,
        content_type='application/json; charset=utf-8',
    )


def _err(code: str, message: str, status: int) -> Response:
    return _json({"error": {"code": code, "message": message}}, status)


def _list_resp(rows, total, limit, offset) -> Response:
    return _json({
        "data": [_row(r) for r in rows],
        "page": {"limit": limit, "offset": offset, "total": total},
    })


def _guard(user_id: int):
    """경로 userId 와 JWT user_id 일치 검증. 불일치 시 403 응답 반환, 통과 시 None."""
    if int(user_id) != int(g.current_user_id):
        return _err("FORBIDDEN", "본인 계좌만 조회할 수 있습니다.", 403)
    return None


def _page():
    """limit/offset 파싱 + 검증. limit 은 MAX_LIMIT 로 상한, offset 은 0 이상."""
    limit = min(max(int(request.args.get("limit", 20)), 1), MAX_LIMIT)
    offset = max(int(request.args.get("offset", 0)), 0)
    return limit, offset


# ===============================================================================
# 0. PING
# ===============================================================================
@account_trade_bp.route("/ping", methods=['GET'])
def account_trade_ping():
    return {'msg': 'aibees flask :: users account/trade home'}


# ===============================================================================
# ① 계좌 요약  GET /api/v1/users/<userId>/account
# ===============================================================================
@account_trade_bp.route("/<int:user_id>/account", methods=['GET'])
@require_auth
def get_account(user_id):
    if (err := _guard(user_id)):
        return err
    try:
        row = accountTradeDaoImpl.get_wallet(g.db, user_id)
        if not row:
            return _err("NOT_FOUND", "계좌 정보가 없습니다.", 404)
        return _json(_row(row))
    except Exception as e:
        logging.exception(e)
        return _err("INTERNAL_ERROR", str(e), 500)


# ===============================================================================
# ② 보유 포트폴리오  GET /api/v1/users/<userId>/portfolio
# ===============================================================================
@account_trade_bp.route("/<int:user_id>/portfolio", methods=['GET'])
@require_auth
def get_portfolio(user_id):
    if (err := _guard(user_id)):
        return err
    try:
        rows = accountTradeDaoImpl.get_portfolio(g.db, user_id)

        holdings = []
        for r in rows:
            if r.get("row_type") == "STOCK":
                d = _row(r)
                for k in ("row_type", "cash", "total_asset"):
                    d.pop(k, None)  # 종목 항목엔 노출하지 않음
                holdings.append(d)

        total_row = next((r for r in rows if r.get("row_type") == "TOTAL"), None)
        summary = None
        if total_row:
            summary = _row({
                "cash":         total_row.get("cash"),
                "stock_amount": total_row.get("eval_amount"),
                "total_asset":  total_row.get("total_asset"),
                "updated_at":   total_row.get("updated_at"),
            })

        return _json({"holdings": holdings, "summary": summary})
    except Exception as e:
        logging.exception(e)
        return _err("INTERNAL_ERROR", str(e), 500)


# ===============================================================================
# ③ worker 포지션  GET /api/v1/users/<userId>/positions?status=&limit=&offset=
# ④ worker 매매 이력 GET /api/v1/users/<userId>/positions/history?status=&limit=&offset=
#    → 동일 스키마. status 파라미터만 그대로 전달.
# ===============================================================================
_VALID_POSITION_STATUS = (None, "HOLDING", "SOLD")


def _positions_common(user_id):
    if (err := _guard(user_id)):
        return err
    status = request.args.get("status") or None
    if status not in _VALID_POSITION_STATUS:
        return _err("INVALID_PARAM", "status 는 HOLDING | SOLD 만 허용됩니다.", 400)
    limit, offset = _page()
    rows, total = accountTradeDaoImpl.get_positions(g.db, user_id, status, limit, offset)
    return _list_resp(rows, total, limit, offset)


@account_trade_bp.route("/<int:user_id>/positions", methods=['GET'])
@require_auth
def get_positions(user_id):
    try:
        return _positions_common(user_id)
    except Exception as e:
        logging.exception(e)
        return _err("INTERNAL_ERROR", str(e), 500)


@account_trade_bp.route("/<int:user_id>/positions/history", methods=['GET'])
@require_auth
def get_positions_history(user_id):
    try:
        return _positions_common(user_id)
    except Exception as e:
        logging.exception(e)
        return _err("INTERNAL_ERROR", str(e), 500)


# ===============================================================================
# ⑤ 거래(체결) 로그
#    GET /api/v1/users/<userId>/trade-logs?action=&stock_code=&from=&to=&limit=&offset=
# ===============================================================================
@account_trade_bp.route("/<int:user_id>/trade-logs", methods=['GET'])
@require_auth
def get_trade_logs(user_id):
    if (err := _guard(user_id)):
        return err

    action = request.args.get("action") or None
    if action not in (None, "BUY", "SELL"):
        return _err("INVALID_PARAM", "action 은 BUY | SELL 만 허용됩니다.", 400)

    try:
        limit, offset = _page()
        rows, total = accountTradeDaoImpl.get_trade_logs(
            g.db, user_id,
            action=action,
            code=request.args.get("stock_code") or None,
            dt_from=request.args.get("from"),
            dt_to=request.args.get("to"),
            limit=limit, offset=offset,
        )
        return _list_resp(rows, total, limit, offset)
    except ValueError:
        return _err("INVALID_PARAM", "from / to 기간 형식이 올바르지 않습니다.", 400)
    except Exception as e:
        logging.exception(e)
        return _err("INTERNAL_ERROR", str(e), 500)


# ===============================================================================
# ⑥ 운영 로그
#    GET /api/v1/users/<userId>/worker-logs?source=&level=&from=&limit=&offset=
# ===============================================================================
@account_trade_bp.route("/<int:user_id>/worker-logs", methods=['GET'])
@require_auth
def get_worker_logs(user_id):
    if (err := _guard(user_id)):
        return err

    source = request.args.get("source") or None
    if source not in (None, "buy", "sell"):
        return _err("INVALID_PARAM", "source 는 buy | sell 만 허용됩니다.", 400)

    level = request.args.get("level") or None
    if level not in (None, "INFO", "WARN"):
        return _err("INVALID_PARAM", "level 은 INFO | WARN 만 허용됩니다.", 400)

    try:
        limit, offset = _page()
        rows, total = accountTradeDaoImpl.get_worker_logs(
            g.db, user_id,
            source=source,
            level=level,
            dt_from=request.args.get("from"),
            limit=limit, offset=offset,
        )
        return _list_resp(rows, total, limit, offset)
    except ValueError:
        return _err("INVALID_PARAM", "from 기간 형식이 올바르지 않습니다.", 400)
    except Exception as e:
        logging.exception(e)
        return _err("INTERNAL_ERROR", str(e), 500)
