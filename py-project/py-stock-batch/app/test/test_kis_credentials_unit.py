"""
stock_shared.kis (credentials / client) 단위 검증 — DB / KIS 불필요.

무엇을 검증하나
    1. KisCredentialError 가 LookupError 이면서 ValueError 인가
       (naver router_profit 은 `except ValueError` 로 400 을 만들고, batch 는 LookupError 를 기대했다)
    2. load_creds_from_db — 레코드 없음 / 키 비어 있음 / strict 차이 / 공백 제거 / 복호화 주입·실패
       + legacy_fallback(naver 임시 옵션): 화면이 등록한 쌍이 완전할 때만 우선, 한쪽만 있으면 무시
    3. resolve_kis_creds — user_id·env 우선순위, DB 실패 시 파일 폴백, 폴백 끄기
    4. 호출자의 스레드 로컬 세션(dbConn.get_session)을 건드리지 않는가
    5. load_creds_from_file — 파일 없음 / JSON 오류
    6. list_kis_user_ids — 정수·정렬
    7. create_pykis — 생성자 인자 매핑(실전 / 모의 동시)
    8. batch keyLoader 어댑터가 AES 복호화를 주입하는가

실행
    poetry run python -m app.test.test_kis_credentials_unit
"""
import json
import logging
import os
import sys
import tempfile
import types

import stock_shared.kis.credentials as C
from stock_shared.kis.client import create_pykis

PASS, FAIL = [], []


def check(name: str, cond: bool, detail: str = ''):
    (PASS if cond else FAIL).append(name)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ''))


# ── 가짜 DB ───────────────────────────────────────────────────────────────
class _Row:
    def __init__(self, **kw):
        self.__dict__.update(kw)

    @property
    def _mapping(self):       # SQLAlchemy Row._mapping 흉내 — 코드가 컬럼명으로 접근한다
        return self.__dict__


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def first(self):
        return self._rows[0] if self._rows else None

    def scalars(self):
        return self

    def all(self):
        return self._rows


def fake_session_returning(rows):
    """C.Session(dbConn.engine) 를 대체. with 문으로 쓰이므로 컨텍스트 매니저 흉내."""
    class _S:
        def __init__(self, *_a, **_k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def execute(self, *_a, **_k): return _Result(rows)
    return _S


def row(**over):
    base = dict(kis_id='hts_id', kis_account='12345678-01',
                kis_app_key='A' * 36, kis_sec_key='S' * 180,
                kis_access_key='', kis_secret_key='')     # 낡은 컬럼(사용자 설정 화면이 쓰는 쪽)
    base.update(over)
    return _Row(**base)


def with_db(rows):
    C.Session = fake_session_returning(rows)


def raises(fn, exc):
    try:
        fn()
    except exc as e:
        return True, e
    except Exception as e:  # noqa: BLE001
        return False, e
    return False, None


def main():
    real_session = C.Session

    # 1) 예외 타입 ──────────────────────────────────────────────────────────
    print('\n[1] KisCredentialError 호환성')
    e = C.KisCredentialError('x')
    check('LookupError 이다 (batch 호환)', isinstance(e, LookupError))
    check('ValueError 이다 (naver router_profit 의 except ValueError)', isinstance(e, ValueError))

    # 2) load_creds_from_db ─────────────────────────────────────────────────
    print('\n[2] load_creds_from_db')
    with_db([])
    ok, err = raises(lambda: C.load_creds_from_db(9), C.KisCredentialError)
    check('레코드 없음 → KisCredentialError', ok)
    check('  메시지에 user_id 포함', ok and 'user_id=9' in str(err) and '레코드를 찾을 수 없습니다' in str(err))

    with_db([row(kis_app_key='')])
    ok, _ = raises(lambda: C.load_creds_from_db(1), C.KisCredentialError)
    check('app_key 비어 있음 → 예외', ok)
    with_db([row(kis_app_key='   ')])
    ok, _ = raises(lambda: C.load_creds_from_db(1), C.KisCredentialError)
    check('app_key 공백만 → 비어 있는 것으로 취급 (list_kis_user_ids 의 TRIM 과 일치)', ok)

    with_db([row(kis_sec_key='')])
    out = C.load_creds_from_db(1)
    check('lenient: sec_key 비어도 통과 (예전 batch 동작 — 폴백 사유를 늘리지 않으려는 의도)',
          out['app_key'] == 'A' * 36 and out['sec_key'] == '')
    ok, err = raises(lambda: C.load_creds_from_db(1, strict=True), C.KisCredentialError)
    check('strict: sec_key 비어 있으면 예외 (예전 naver 동작)', ok and '인증키가 설정되지 않았습니다' in str(err))

    with_db([row(kis_account='')])
    check('lenient: account 비어도 통과', C.load_creds_from_db(1)['account'] == '')
    ok, err = raises(lambda: C.load_creds_from_db(1, strict=True), C.KisCredentialError)
    check('strict: account 비어 있으면 예외', ok and 'kis_id/kis_account' in str(err))

    with_db([row(kis_app_key='  K' + 'A' * 35 + '  ', kis_sec_key=' ' + 'S' * 180 + '\n')])
    out = C.load_creds_from_db(1)
    check('app_key / sec_key 앞뒤 공백 제거 (복사-붙여넣기 실수 방어)',
          out['app_key'] == 'K' + 'A' * 35 and out['sec_key'] == 'S' * 180)
    check('반환 키 이름은 id/account/app_key/sec_key (KisEngine 이 기대하는 형태)',
          sorted(out) == ['account', 'app_key', 'id', 'sec_key'])

    with_db([row()])
    calls = []
    out = C.load_creds_from_db(1, decrypt=lambda v: calls.append(v) or 'PLAIN-' + v[:2])
    check('decrypt 콜백이 app_key/sec_key 에 적용됨',
          out['app_key'] == 'PLAIN-AA' and out['sec_key'] == 'PLAIN-SS' and len(calls) == 2)

    def boom(_v):
        raise ValueError('bad padding')
    logging.disable(logging.NOTSET)
    out = C.load_creds_from_db(1, decrypt=boom)
    check('복호화 실패 → 평문 그대로 사용 (평문 저장된 정상 키를 막지 않는다)',
          out['app_key'] == 'A' * 36 and out['sec_key'] == 'S' * 180)
    check('decrypt 미지정 → 복호화 시도 없음', C.load_creds_from_db(1)['app_key'] == 'A' * 36)

    print('\n[2b] legacy_fallback — 사용자 설정 화면이 낡은 컬럼에 쓰는 문제 (naver 임시 옵션)')
    LA, LS = 'L' * 36, 'M' * 180
    with_db([row(kis_access_key=LA, kis_secret_key=LS)])
    out = C.load_creds_from_db(1, legacy_fallback=True)
    check('화면이 등록한 쌍이 완전하면 그 쌍을 우선 (예전 naver 동작 — 화면 등록 키가 계속 먹힌다)',
          out['app_key'] == LA and out['sec_key'] == LS)
    out = C.load_creds_from_db(1)
    check('legacy_fallback 꺼져 있으면(batch) 낡은 컬럼은 무시하고 정본 쌍', out['app_key'] == 'A' * 36)

    with_db([row(kis_access_key='', kis_secret_key=LS)])       # user 5 모양: access 는 '', secret 만 있음
    out = C.load_creds_from_db(1, legacy_fallback=True)
    check('한쪽만 있으면(user 5 모양) 낡은 쌍을 쓰지 않고 정본 쌍 — 섞인 쌍 방지',
          out['app_key'] == 'A' * 36 and out['sec_key'] == 'S' * 180)
    with_db([row(kis_access_key=LA, kis_secret_key='   ')])
    out = C.load_creds_from_db(1, legacy_fallback=True)
    check('반대로 access 만 있어도 정본 쌍 (공백만 있는 값도 비어 있는 것)',
          out['app_key'] == 'A' * 36 and out['sec_key'] == 'S' * 180)

    with_db([row(kis_app_key='', kis_sec_key='', kis_access_key=LA, kis_secret_key=LS)])
    out = C.load_creds_from_db(1, legacy_fallback=True, strict=True)
    check('정본 쌍이 비어도 화면 쌍이 완전하면 통과 (화면만으로 등록한 사용자)',
          out['app_key'] == LA and out['sec_key'] == LS)
    with_db([row(kis_app_key='', kis_sec_key='', kis_access_key='', kis_secret_key='')])
    ok, _ = raises(lambda: C.load_creds_from_db(1, legacy_fallback=True, strict=True), C.KisCredentialError)
    check('둘 다 비면 예외', ok)
    with_db([row(kis_app_key='', kis_sec_key='', kis_access_key=LA, kis_secret_key='')])
    ok, _ = raises(lambda: C.load_creds_from_db(1, legacy_fallback=True, strict=True), C.KisCredentialError)
    check('정본이 비고 화면 쌍도 불완전하면 예외 (한쪽 키만으로 통과시키지 않는다)', ok)

    with_db([row(kis_access_key=LA, kis_secret_key=LS)])
    calls2 = []
    C.load_creds_from_db(1, legacy_fallback=True, decrypt=lambda v: calls2.append(v) or v)
    check('선택된 쌍에 decrypt 가 적용된다', calls2 == [LA, LS])
    with_db([row()])

    # 3) resolve_kis_creds ──────────────────────────────────────────────────
    print('\n[3] resolve_kis_creds — 우선순위와 폴백')
    tmpdir = tempfile.mkdtemp()
    kf = os.path.join(tmpdir, 'kis.key')
    json.dump({'id': 'FILE', 'account': 'FILE-ACC', 'app_key': 'FA', 'sec_key': 'FS'}, open(kf, 'w'))
    saved_env = {k: os.environ.pop(k, None) for k in ('KIS_USER_ID', 'KIS_ALLOW_FILE_FALLBACK')}

    with_db([row(kis_id='DBUSER')])
    check('user_id 도 env 도 없으면 → 파일', C.resolve_kis_creds(None, kf)['id'] == 'FILE')
    check('user_id 인자가 있으면 → DB', C.resolve_kis_creds(1, kf)['id'] == 'DBUSER')

    os.environ['KIS_USER_ID'] = '3'
    check('user_id 없고 KIS_USER_ID env 가 있으면 → DB', C.resolve_kis_creds(None, kf)['id'] == 'DBUSER')
    os.environ.pop('KIS_USER_ID')

    with_db([])  # DB 에 없음
    check('DB 실패 → 파일 폴백 (기본 허용)', C.resolve_kis_creds(5, kf)['id'] == 'FILE')
    os.environ['KIS_ALLOW_FILE_FALLBACK'] = 'false'
    ok, _ = raises(lambda: C.resolve_kis_creds(5, kf), C.KisCredentialError)
    check('KIS_ALLOW_FILE_FALLBACK=false → 폴백 안 하고 예외 전파', ok)
    for v in ('0', 'no', 'off'):
        os.environ['KIS_ALLOW_FILE_FALLBACK'] = v
        ok, _ = raises(lambda: C.resolve_kis_creds(5, kf), C.KisCredentialError)
        check(f'  KIS_ALLOW_FILE_FALLBACK={v!r} 도 끔으로 해석', ok)
    os.environ['KIS_ALLOW_FILE_FALLBACK'] = 'true'
    check('KIS_ALLOW_FILE_FALLBACK=true → 폴백', C.resolve_kis_creds(5, kf)['id'] == 'FILE')
    os.environ.pop('KIS_ALLOW_FILE_FALLBACK')

    # 엄격 로더는 어떤 경우에도 파일로 새지 않는다 (naver 의 안전 속성)
    with_db([])
    ok, _ = raises(lambda: C.load_creds_from_db(5, strict=True), C.KisCredentialError)
    check('load_creds_from_db 는 DB 실패 시 파일로 폴백하지 않는다 (키 없는 유저가 다른 계좌를 보면 안 됨)', ok)

    for k, v in saved_env.items():
        if v is not None:
            os.environ[k] = v

    # 4) 호출자 세션 불간섭 ─────────────────────────────────────────────────
    print('\n[4] 호출자의 스레드 로컬 세션 불간섭')
    with_db([row()])
    touched = []
    real_get = C.dbConn.get_session
    C.dbConn.get_session = lambda: touched.append(1) or (_ for _ in ()).throw(AssertionError('호출자 세션 접근'))
    try:
        C.load_creds_from_db(1)
        check('load_creds_from_db 가 dbConn.get_session()(스레드 로컬 세션)을 쓰지 않는다', not touched)
        C.Session = fake_session_returning([1, 2])
        C.list_kis_user_ids()
        check('list_kis_user_ids 도 스레드 로컬 세션을 쓰지 않는다', not touched)
    finally:
        C.dbConn.get_session = real_get

    # 5) 파일 로더 ──────────────────────────────────────────────────────────
    print('\n[5] load_creds_from_file')
    ok, err = raises(lambda: C.load_creds_from_file(os.path.join(tmpdir, 'nope.key')), FileNotFoundError)
    check('파일 없음 → FileNotFoundError', ok and '찾을 수 없습니다' in str(err))
    bad = os.path.join(tmpdir, 'bad.key')
    open(bad, 'w').write('{not json')
    ok, err = raises(lambda: C.load_creds_from_file(bad), ValueError)
    check('JSON 오류 → ValueError', ok and 'JSON 형식' in str(err))
    check('파일 키 이름을 바꾸지 않는다 (naver 모의투자 파일의 virtual_* 보존)',
          set(C.load_creds_from_file(kf)) == {'id', 'account', 'app_key', 'sec_key'})

    # 6) list_kis_user_ids ──────────────────────────────────────────────────
    print('\n[6] list_kis_user_ids')
    C.Session = fake_session_returning([1, 2, 5])
    ids = C.list_kis_user_ids()
    check('정수 리스트로 반환', ids == [1, 2, 5] and all(isinstance(i, int) for i in ids))
    C.Session = fake_session_returning(['3', '4'])
    check('문자열이 와도 int 로 정규화', C.list_kis_user_ids() == [3, 4])

    # 7) create_pykis ───────────────────────────────────────────────────────
    print('\n[7] create_pykis — 생성자 인자 매핑')
    captured = {}

    class FakePyKis:
        def __init__(self, **kw):
            captured.clear()
            captured.update(kw)

    fake_mod = types.ModuleType('pykis')
    fake_mod.PyKis = FakePyKis
    orig_pykis = sys.modules.get('pykis')      # 이미 import 돼 있었다면 같은 객체로 복구한다
    sys.modules['pykis'] = fake_mod
    try:
        create_pykis(id='i', account='a', app_key='ak', sec_key='sk')
        check('실전: id/account/appkey/secretkey/keep_token=True 만 전달 (virtual_* 없음)',
              captured == dict(id='i', account='a', appkey='ak', secretkey='sk', keep_token=True))
        create_pykis(id='i', account='va', app_key='ak', sec_key='sk',
                     virtual_id='vi', virtual_app_key='vak', virtual_sec_key='vsk')
        check('모의 동시: virtual_id/virtual_appkey/virtual_secretkey 로 매핑',
              captured == dict(id='i', account='va', appkey='ak', secretkey='sk', keep_token=True,
                               virtual_id='vi', virtual_appkey='vak', virtual_secretkey='vsk'))
        create_pykis(id='i', account='a', app_key='ak', sec_key='sk', keep_token=False)
        check('keep_token 을 끌 수 있음', captured['keep_token'] is False)
    finally:
        if orig_pykis is not None:
            sys.modules['pykis'] = orig_pykis
        else:
            sys.modules.pop('pykis', None)

    # 8) batch 어댑터 ───────────────────────────────────────────────────────
    print('\n[8] batch keyLoader 어댑터')
    from app.common.utils.aesUtils import aesUtils
    import app.ext_services.kis.keyLoader as KL
    seen = {}
    real_resolve = KL._resolve_kis_creds
    KL._resolve_kis_creds = lambda uid, kp, decrypt=None: seen.update(uid=uid, kp=kp, decrypt=decrypt) or {'ok': 1}
    try:
        KL.resolve_kis_creds(7, 'x.key')
    finally:
        KL._resolve_kis_creds = real_resolve
    check('AES 복호화(aesUtils.decrypt)를 shared 에 주입한다', seen.get('decrypt') == aesUtils.decrypt)
    check('user_id / key_path 를 그대로 전달', seen.get('uid') == 7 and seen.get('kp') == 'x.key')
    check('list_kis_user_ids 를 재노출 (기존 import 경로 유지)', KL.list_kis_user_ids is C.list_kis_user_ids)

    C.Session = real_session
    print('\n' + '=' * 70)
    print(f'PASS {len(PASS)} · FAIL {len(FAIL)}')
    print('=' * 70)
    if FAIL:
        print('실패:', FAIL)
        sys.exit(1)


if __name__ == '__main__':
    main()
