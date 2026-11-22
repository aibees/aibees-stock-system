"""
트레이닝 차트 퀴즈 문제 생성 워커 — 하루 1번(장 마감·일봉 적재 뒤) 문제를 만들고 패턴 통계를 다시 계산한다.
명세: meetings/설계_2026-11-22_트레이닝-화면.md 4장 · sql/yangbong/014 · app/services/training/builder.py

실행
  상시(컨테이너 training-worker):  python -m app.workers.training_worker
      매일 TRAINING_BUILD_TIME(기본 18:30)에 1번 돈다. 마지막 기준일까지 최근 5거래일 중 빠진 날을 채운다.
  한 번만:                          python -m app.workers.training_worker --once [--backfill N] [--per-day N] [--dry-run]
      처음 선적재: --once --backfill 40  (기준일 40거래일 × 하루 12문제 ≈ 480문제)
      --dry-run : DB 에 쓰지 않고 요약만 찍는다(로컬 시험).

설정(공통코드 stock/setting/training → 환경변수 → 기본값, 돌 때마다 다시 읽는다)
  TRAINING_BUILD_TIME     "HH:MM"  기본 18:30
  TRAINING_PER_DAY        기준일 하나에 저장할 문제 수, 기본 12

DB: 하루 1번 전 종목 일봉(약 300만 행)을 한 번에 읽는다(1분 남짓). 연결은 1개만 쓴다(compose DB_POOL_SIZE=1, OVERFLOW=0).
"""
import argparse
import json
import logging
import os
import signal
import sys
import threading
from datetime import datetime, timedelta

log = logging.getLogger("training_worker")

DEFAULT_BUILD_TIME = "18:30"
DEFAULT_PER_DAY = 12
CATCH_UP_DAYS = 5          # 상시 실행에서 빠진 기준일을 이만큼 거슬러 채운다(워커가 며칠 멈췄던 경우)


def _setup_logging():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s", force=True)


def _settings(db) -> dict:
    from web_shared.dao.masterCodesDao import MasterCodesDao
    raw = {}
    session = db.get_session()
    try:
        rows = MasterCodesDao().select_master_code(session, {'system': 'stock', 'source': 'setting', 'category': 'training'})
        raw = {r['code']: r['desc'] for r in rows}
        session.commit()
    except Exception as e:  # noqa: BLE001
        session.rollback()
        log.warning(f"공통코드 stock/setting/training 조회 실패 — 환경변수·기본값 사용: {e}")
    finally:
        session.remove()

    def get(k, default):
        v = raw.get(k)
        return v if v not in (None, '') else os.environ.get(k, default)

    build_time = str(get('TRAINING_BUILD_TIME', DEFAULT_BUILD_TIME)).strip()
    try:
        datetime.strptime(build_time, "%H:%M")
    except ValueError:
        log.warning(f"TRAINING_BUILD_TIME={build_time!r} 형식 오류 — 기본 {DEFAULT_BUILD_TIME}")
        build_time = DEFAULT_BUILD_TIME
    try:
        per_day = max(1, min(50, int(get('TRAINING_PER_DAY', DEFAULT_PER_DAY))))
    except (TypeError, ValueError):
        per_day = DEFAULT_PER_DAY
    return {"build_time": build_time, "per_day": per_day}


def run_once(db, backfill: int, per_day: int, dry_run: bool) -> dict:
    from app.services.training import builder
    session = db.get_session()
    try:
        r = builder.run(session, backfill_days=backfill, per_day=per_day, dry_run=dry_run)
        summary = {k: v for k, v in r.items() if k not in ("stats", "sample")}
        log.info("결과 " + json.dumps(summary, ensure_ascii=False, default=str))
        return r
    except Exception:
        session.rollback()
        raise
    finally:
        session.remove()


def _next_run(build_time: str, now: datetime) -> datetime:
    hh, mm = map(int, build_time.split(":"))
    at = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    return at if at > now else at + timedelta(days=1)


def loop(db):
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    log.info("트레이닝 워커 시작")
    while not stop.is_set():
        conf = _settings(db)
        at = _next_run(conf["build_time"], datetime.now())
        log.info(f"다음 실행 {at:%Y-%m-%d %H:%M} (문제 {conf['per_day']}개/기준일)")
        # 설정이 바뀌어도 반영되게 10분마다 깨어 다시 계산한다
        while not stop.is_set() and datetime.now() < at:
            stop.wait(min(600.0, max(1.0, (at - datetime.now()).total_seconds())))
            if (at - datetime.now()).total_seconds() > 600:
                at = _next_run(_settings(db)["build_time"], datetime.now())
        if stop.is_set():
            break
        try:
            run_once(db, CATCH_UP_DAYS, conf["per_day"], dry_run=False)
        except Exception as e:  # noqa: BLE001
            log.exception(f"문제 생성 실패: {e}")
    log.info("트레이닝 워커 종료")


def main(argv=None):
    _setup_logging()
    ap = argparse.ArgumentParser(description="트레이닝 차트 퀴즈 문제 생성")
    ap.add_argument("--once", action="store_true", help="지금 한 번만 돌고 끝낸다")
    ap.add_argument("--backfill", type=int, default=CATCH_UP_DAYS, help="거슬러 만들 기준일 수(--once)")
    ap.add_argument("--per-day", type=int, default=None, help="기준일 하나에 저장할 문제 수(기본 공통코드)")
    ap.add_argument("--dry-run", action="store_true", help="DB 에 쓰지 않는다")
    args = ap.parse_args(argv)

    from stock_shared.db.database import dbConn
    if not args.once:
        loop(dbConn)
        return 0
    per_day = args.per_day or _settings(dbConn)["per_day"]
    run_once(dbConn, max(1, args.backfill), per_day, args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
