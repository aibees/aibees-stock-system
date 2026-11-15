"""
collect_wave2_minutes.py — 2파 신호(최근 약 1년)의 보유 구간 1분봉 수집. 장중 꺾임 판독 검증용.

대상: bt_wave2_fake_rise 결과(fake_rise.pkl) 중 FROM 이후 신호, 신호일 포함 직전 WARMUP 거래일(분봉 지표 예열용)부터 base15 종료일까지.
저장: bt_reco_cache/minute/{code}/{YYYYMMDD}.pkl — 이미 있는 날은 건너뛰므로 중단 후 다시 실행해도 된다.
조회 전용(주문 없음). 분당 호출을 묶어 초당 RATE 회 이하로 제한하고, 장 시작 전 STOP_AT 에 스스로 멈춘다.
정상 하루는 약 381분. MIN_BARS 미만은 저장하지 않고(요청 실패와 무거래를 구분할 수 없음) 실패 목록에 남긴다.

사용
    poetry run python -m app.test.collect_wave2_minutes [--limit N]
"""
import argparse
import os
import sys
import time
from datetime import datetime

import pandas as pd

sys.path.insert(0, '../shared')

from app.ext_services.kis.KisEngine import KisEngine
from app.test.bt_wave2_fake_rise import CACHE
from app.test.bt_wave2_trendline import OUT as W2

FROM = '2025-11-10'
OUT = os.path.join(CACHE, 'minute')
RATE = 8
MIN_BARS = 100
STOP_AT = '08:30'
WARMUP = 3


def targets(warmup=WARMUP, signal_only=False):
    """signal_only: 보유 구간 대신 신호일까지만(신호일 포함 직전 warmup 거래일). 분봉 순위 연구(bt_private_intraday)용."""
    tr = pd.read_pickle(os.path.join(W2, 'fake_rise.pkl'))
    tr = tr[tr.date >= FROM]
    days = set()
    for code, g in tr.groupby('code'):
        df = pd.read_pickle(os.path.join(CACHE, 'stocks', f'{code}.pkl'))
        dates = df['datetime'].astype(str).str[:10].tolist()
        idx = {d: k for k, d in enumerate(dates)}
        for s in g.itertuples():
            i = idx[s.date]
            last = 0 if signal_only else int(s.end_d)
            days.update((code, dates[i + d].replace('-', '')) for d in range(1 - warmup, last + 1) if i + d >= 0)
    return sorted(days), len(tr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int)
    ap.add_argument('--warmup', type=int, default=WARMUP, help='신호일 포함 직전 거래일 수')
    ap.add_argument('--signal-only', action='store_true', help='보유 구간은 빼고 신호일까지만')
    args = ap.parse_args()
    days, n_sig = targets(args.warmup, args.signal_only)
    todo = [(c, d) for c, d in days if not os.path.exists(os.path.join(OUT, c, f'{d}.pkl'))]
    print(f'신호 {n_sig}건 / 대상 {len(days)}종목일 / 남은 {len(todo)}', flush=True)
    if args.limit:
        todo = todo[:args.limit]
    eng = KisEngine()
    raw, calls, gap = eng._fetch_day_minutes_page, [0], 1 / RATE

    def paced(*a):
        calls[0] += 1
        time.sleep(gap)
        return raw(*a)
    eng._fetch_day_minutes_page = paced

    failed, t0 = [], time.time()
    for n, (code, ymd) in enumerate(todo, 1):
        if datetime.now().strftime('%H:%M') >= STOP_AT and datetime.now().hour < 16:
            print(f'{STOP_AT} 도달 — 장 시작 전 중단. 다시 실행하면 이어서 받는다.', flush=True)
            break
        try:
            df = eng.fetch_day_minutes(code, ymd)
        except Exception as e:  # noqa: BLE001
            print(f'실패 {code} {ymd}: {type(e).__name__}: {e}', flush=True)
            df = pd.DataFrame()
        if len(df) >= MIN_BARS:
            os.makedirs(os.path.join(OUT, code), exist_ok=True)
            df.to_pickle(os.path.join(OUT, code, f'{ymd}.pkl'))
        else:
            failed.append((code, ymd, len(df)))
        if n % 100 == 0:
            print(f'{n}/{len(todo)} 호출 {calls[0]} 실패 {len(failed)} {time.time() - t0:.0f}초', flush=True)
    pd.DataFrame(failed, columns=['code', 'ymd', 'bars']).to_csv(os.path.join(OUT, 'failed.csv'), index=False) if os.path.isdir(OUT) else None
    print(f'완료: 처리 {n if todo else 0} / 호출 {calls[0]} / 실패 {len(failed)} / {time.time() - t0:.0f}초', flush=True)


if __name__ == '__main__':
    main()
