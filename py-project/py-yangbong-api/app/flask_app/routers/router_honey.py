"""
router_honey.py — 꿀(포인트) 1단계 API. **양봉상회 전용**(2026-11-22). 규칙은 app/services/honey_service.py.

    GET  /api/v1/honey                 요약(잔액·오늘 모은 양·할 일 상태·연속 출석·하루 이용권)
    GET  /api/v1/honey/ledger          꿀 내역(최근순, ?before=<id>&limit=50)
    POST /api/v1/honey/attend          오늘 출석(7일 연속이면 보너스)
    POST /api/v1/honey/quiz            오늘의 한 문제 정답(하루 1번)
    POST /api/v1/honey/start           처음 시작하기 완료(1번)
    POST /api/v1/honey/spend           body {item:'DAY_PASS'} — 프리미엄 하루 이용권
    GET  /api/v1/honey/admob-ssv       AdMob 보상형 광고 서버 측 확인(SSV) 콜백. 로그인 없이 Google 이 부른다.
    GET  /api/v1/honey/invite          친구 초대(2단계): 내 코드·초대 현황·내가 넣은 코드 진행(sql/yangbong/013)
    POST /api/v1/honey/invite/redeem   body {code, deviceId} — 친구 코드 넣기. 3일 출석하면 양쪽에 꿀

수업 완료 꿀은 학습 기록 API(router_training POST /training/progress)가 단계를 저장할 때 함께 준다.
위 POST 는 모두 로그인 필요. 응답은 언제나 갱신된 요약 + 이번에 받은 꿀(gained).

광고 꿀은 앱이 아니라 Google 이 이 서버에 직접 알려 줄 때만 준다(앱 조작으로 꿀을 찍어 내지 못하게).
  AdMob 콘솔 > 광고 단위(보상형) > 서버 측 확인 URL = https://<양봉 API>/api/v1/honey/admob-ssv
  앱은 광고를 불러올 때 ssv.userId = 로그인 user_id 를 넣는다(useAdMob.loadRewardedAd).
"""
import base64
import logging
import time
from urllib.parse import parse_qs, unquote

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from flask import Blueprint, g, request

from app.services import honey_service as honey
from web_shared.auth.decorators import require_auth
from web_shared.http.response import ApiResponse

honey_bp = Blueprint("honey", __name__)


def _ok(user_id, gained=0, **extra):
    data = {"summary": honey.summary(g.db, user_id), "gained": gained}
    data.update(extra)
    return ApiResponse.success(data)


@honey_bp.route("/honey", methods=['GET'])
@require_auth
def get_honey():
    try:
        return ApiResponse.success(honey.summary(g.db, g.current_user_id))
    except Exception as e:
        logging.exception(e)
        return ApiResponse.error("꿀 정보를 불러오지 못했어요.")


@honey_bp.route("/honey/ledger", methods=['GET'])
@require_auth
def get_ledger():
    try:
        before = request.args.get('before', type=int)
        limit = request.args.get('limit', default=50, type=int)
        return ApiResponse.success(honey.ledger(g.db, g.current_user_id, limit, before))
    except Exception as e:
        logging.exception(e)
        return ApiResponse.error("꿀 내역을 불러오지 못했어요.")


def _write(fn):
    try:
        result = fn()
        g.db.commit()
        return result
    except honey.HoneyError:
        g.db.rollback()
        raise
    except Exception:
        g.db.rollback()
        raise


@honey_bp.route("/honey/attend", methods=['POST'])
@require_auth
def post_attend():
    try:
        r = _write(lambda: honey.attend(g.db, g.current_user_id))
        return _ok(g.current_user_id, r["got"] + r["bonus"], bonus=r["bonus"])
    except Exception as e:
        logging.exception(e)
        return ApiResponse.error("출석을 기록하지 못했어요.")


@honey_bp.route("/honey/quiz", methods=['POST'])
@require_auth
def post_quiz():
    # 정답 여부는 화면이 판정한다(오늘의 문제는 화면 데이터). 하루 1번·10꿀이라 위험이 작다.
    body = request.get_json(silent=True) or {}
    if body.get('correct') is not True:
        return ApiResponse.error("정답일 때만 꿀을 받아요.", status=400)
    try:
        today = honey.ymd_of(honey.now_kst())
        got = _write(lambda: honey.credit(g.db, g.current_user_id, 'QUIZ', today, honey.QUIZ))
        return _ok(g.current_user_id, got)
    except Exception as e:
        logging.exception(e)
        return ApiResponse.error("꿀을 받지 못했어요.")


@honey_bp.route("/honey/start", methods=['POST'])
@require_auth
def post_start():
    try:
        got = _write(lambda: honey.credit(g.db, g.current_user_id, 'START', 'first', honey.START))
        return _ok(g.current_user_id, got)
    except Exception as e:
        logging.exception(e)
        return ApiResponse.error("꿀을 받지 못했어요.")


@honey_bp.route("/honey/spend", methods=['POST'])
@require_auth
def post_spend():
    body = request.get_json(silent=True) or {}
    if body.get('item') != 'DAY_PASS':
        return ApiResponse.error("쓸 수 없는 항목이에요.", status=400)
    try:
        _write(lambda: honey.buy_day_pass(g.db, g.current_user_id))
        return _ok(g.current_user_id, -honey.DAY_PASS_COST)
    except honey.HoneyError as e:
        return ApiResponse.error(str(e), status=409)
    except Exception as e:
        logging.exception(e)
        return ApiResponse.error("꿀을 쓰지 못했어요.")


@honey_bp.route("/honey/invite", methods=['GET'])
@require_auth
def get_invite():
    try:
        data = _write(lambda: honey.invite_summary(g.db, g.current_user_id))   # 코드가 없으면 만든다
        return ApiResponse.success(data)
    except Exception as e:
        logging.exception(e)
        return ApiResponse.error("초대 정보를 불러오지 못했어요.")


@honey_bp.route("/honey/invite/redeem", methods=['POST'])
@require_auth
def post_invite_redeem():
    body = request.get_json(silent=True) or {}
    try:
        r = _write(lambda: honey.redeem_invite(g.db, g.current_user_id, body.get('code'), body.get('deviceId')))
        return ApiResponse.success({"invite": honey.invite_summary(g.db, g.current_user_id),
                                    "summary": honey.summary(g.db, g.current_user_id), "gained": (r or {}).get("gained", 0)})
    except honey.HoneyError as e:
        return ApiResponse.error(str(e), status=409)
    except Exception as e:
        logging.exception(e)
        return ApiResponse.error("초대 코드를 등록하지 못했어요.")


# ── AdMob 서버 측 확인(SSV) ────────────────────────────────
# https://developers.google.com/admob/android/ssv — 서명은 쿼리 문자열 중 '&signature=' 앞부분을 ECDSA(SHA-256)로 검증한다.
_KEYS_URL = 'https://www.gstatic.com/admob/reward/verifier-keys.json'
_KEYS_TTL = 24 * 3600
_keys = {"at": 0.0, "by_id": {}}


def _verifier_key(key_id: str):
    if time.time() - _keys["at"] > _KEYS_TTL or key_id not in _keys["by_id"]:
        data = requests.get(_KEYS_URL, timeout=5).json()
        _keys["by_id"] = {str(k["keyId"]): k["pem"] for k in data.get("keys", [])}
        _keys["at"] = time.time()
    pem = _keys["by_id"].get(str(key_id))
    return serialization.load_pem_public_key(pem.encode()) if pem else None


def _verify_ssv(query: str) -> dict:
    """서명이 맞으면 쿼리 값들을 돌려준다. 틀리면 ValueError."""
    marker = '&signature='
    idx = query.find(marker)
    if idx < 0:
        raise ValueError("signature 없음")
    message = query[:idx].encode()
    params = {k: v[0] for k, v in parse_qs(query, keep_blank_values=True).items()}
    sig = params.get('signature', '')
    sig_bytes = base64.urlsafe_b64decode(sig + '=' * (-len(sig) % 4))
    key = _verifier_key(params.get('key_id', ''))
    if key is None:
        raise ValueError("알 수 없는 key_id")
    key.verify(sig_bytes, message, ec.ECDSA(hashes.SHA256()))
    return params


@honey_bp.route("/honey/admob-ssv", methods=['GET'])
def admob_ssv():
    # Google 은 200 이 아니면 다시 보낸다. 서명이 틀린 요청에는 꿀을 주지 않고 400.
    try:
        params = _verify_ssv(request.query_string.decode())
    except Exception as e:
        logging.warning(f"[honey] SSV 검증 실패: {e}")
        return ApiResponse.error("invalid", status=400)
    try:
        user_id = int(unquote(params.get('user_id', '')))
    except ValueError:
        return ApiResponse.success(None)   # 로그인하지 않고 본 광고 — 꿀 없음(Google 에는 200)
    tx = params.get('transaction_id', '')
    if not tx:
        return ApiResponse.error("invalid", status=400)
    try:
        got = _write(lambda: honey.watch_ad(g.db, user_id, tx))
        logging.info(f"[honey] 광고 꿀 user_id={user_id} tx={tx[:12]} got={got}")
        return ApiResponse.success(None)
    except Exception as e:
        logging.exception(e)
        return ApiResponse.error("error", status=500)
