"""
worker 로그 DB 적재 범위 단위 검증 — DB / KIS 불필요.

2026-11-17 사용자 요청: trade_worker_log 에는 실제 매수/매도 체결, 설정값 변경, 지정가 동기화만 남긴다.

무엇을 검증하나
    1. WorkerLogger — info/warn 은 DB 에 안 쓰고, fill/setting/limit_sync 만 쓴다(level 포함)
    2. reload_manual_sells — 기동 후 첫 적재는 DB 에 안 남김, 이후 등록·가격 변경·해제만 남김,
       변화 없으면 아무것도 안 남김, 부분체결로 filled_qty 만 바뀐 건 변경이 아님
    3. DB 기록이 실패해도 예외가 밖으로 안 나간다(매매 흐름 보호)

실행
    poetry run python -m app.test.test_worker_log_unit
"""
import sys
import threading
from decimal import Decimal

from app.trade_worker.sell_executor import BaseSellExecutor
from app.trade_worker.worklog import WorkerLogger

PASS, FAIL = [], []


def check(name, cond, detail=''):
    (PASS if cond else FAIL).append(name)
    print(('  PASS ' if cond else '  FAIL ') + name + (f'  -- {detail}' if detail and not cond else ''))


class FakeRepo:
    def __init__(self):
        self.logs = []
        self.manual = []
        self.fail = False

    def insert_worker_log(self, uid, src, lvl, msg):
        if self.fail:
            raise RuntimeError('db down')
        self.logs.append((uid, src, lvl, msg))

    def get_active_manual_sells(self, uid):
        return [dict(r) for r in self.manual]


def test_logger():
    print('\n[1] WorkerLogger 적재 범위')
    repo = FakeRepo()
    w = WorkerLogger(repo, 7, 'buy', echo=False)
    w.info('[매수] 후보 없음')
    w.warn('[매수] 시세 조회 실패: %s', 'x')
    w.warning('[매수] 별칭')
    check('info/warn/warning 은 DB 에 안 씀', repo.logs == [])
    w.fill('[매수] 완료 %s qty=%s', '005930', 3)
    w.setting('[설정] 변경 감지 → 전략 재적용 (%s)', 'a: 1→2')
    w.setting('[설정] 운용모드 %s → %s 전환 실패', 'RECO', 'X', level='WARN')
    w.limit_sync('[지정가] %s 수기등록 반영', '101730')
    check('fill/setting/limit_sync 4건 적재', len(repo.logs) == 4, repo.logs)
    check('포맷 적용', repo.logs[0] == (7, 'buy', 'INFO', '[매수] 완료 005930 qty=3'), repo.logs[0])
    check('setting level=WARN 반영', repo.logs[2][2] == 'WARN')
    repo.fail = True
    try:
        w.fill('[매도] 완료 %s', '000660')
        ok = True
    except Exception:  # noqa: BLE001
        ok = False
    check('DB 실패해도 예외 안 나감', ok)


class Exec(BaseSellExecutor):
    def __init__(self, repo):
        self.repo = repo
        self.cfg = type('C', (), {'user_id': 7})()
        self._lock = threading.Lock()
        self._manual_sells = {}
        self._manual_loaded = False
        self.positions = {'101730': {}, '005930': {}}
        self.wlog = WorkerLogger(repo, 7, 'sell', echo=False)


def T(id_, code, price, trig='UP', filled=0):
    return {'id': id_, 'stock_code': code, 'sell_price': Decimal(str(price)), 'trigger_type': trig,
            'filled_qty': Decimal(filled)}


def test_manual_sync():
    print('\n[2] 수기 지정가 동기화 로그')
    Exec.__abstractmethods__ = frozenset()
    repo = FakeRepo()
    ex = Exec(repo)
    repo.manual = [T(1, '101730', 5120, 'DOWN'), T(2, '101730', 7000)]
    ex.reload_manual_sells()
    check('기동 후 첫 적재 → DB 로그 없음', repo.logs == [], repo.logs)
    check('첫 적재도 메모리엔 반영', set(ex._manual_sells) == {'101730'})

    ex.reload_manual_sells()
    check('변화 없음 → 로그 없음', repo.logs == [])

    repo.manual.append(T(3, '005930', 80000))
    ex.reload_manual_sells()
    check('새 종목 등록 → 1건(반영)', len(repo.logs) == 1 and '005930' in repo.logs[0][3] and '반영' in repo.logs[0][3],
          repo.logs)

    repo.logs.clear()
    repo.manual[1] = T(2, '101730', 7200)
    ex.reload_manual_sells()
    check('가격 변경 → 1건(변경)', len(repo.logs) == 1 and '101730' in repo.logs[0][3] and '변경' in repo.logs[0][3],
          repo.logs)

    repo.logs.clear()
    ex._manual_sells['101730'][0]['filled_qty'] = Decimal(5)    # 부분체결로 메모리 값만 변함
    ex.reload_manual_sells()
    check('filled_qty 변화는 변경 아님', repo.logs == [], repo.logs)

    repo.manual = [r for r in repo.manual if r['stock_code'] != '005930']
    ex.reload_manual_sells()
    check('해제 → 1건(해제)', len(repo.logs) == 1 and '005930' in repo.logs[0][3] and '해제' in repo.logs[0][3],
          repo.logs)

    repo.logs.clear()
    repo.manual.append(T(9, '999990', 1000))   # 아직 포지션 편입 전 종목
    ex.reload_manual_sells()
    check('편입 전 종목 등록도 지정가 동기화로 1건', len(repo.logs) == 1 and '편입 전' in repo.logs[0][3], repo.logs)
    check('지정가 로그 source=sell, level=INFO', repo.logs[0][1:3] == ('sell', 'INFO'))


if __name__ == '__main__':
    test_logger()
    test_manual_sync()
    print(f'\n결과: PASS {len(PASS)} / FAIL {len(FAIL)}')
    if FAIL:
        print('ALL FAIL 목록:', FAIL)
        sys.exit(1)
    print('ALL PASS')
