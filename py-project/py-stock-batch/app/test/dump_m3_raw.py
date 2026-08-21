"""
30분봉 수집 파이프라인 단계별 덤프 — 어디서 깨지는지 눈으로 확인한다.

집계가 틀어졌을 때 코드만 봐서는 원인을 못 잡는다. 실제 API 응답부터
1분봉 DataFrame, 30분봉 집계까지 각 단계를 그대로 찍어서 비교한다.

확인 포인트
    [1] 원시 응답    — output2 행 수(=페이지 크기), 필드명, 시각 형식,
                       요청 날짜와 응답 날짜가 같은가
    [2] 페이지네이션 — 커서를 내려가며 몇 번 만에 09:00 에 닿는가,
                       총 몇 분을 모았는가 (정상 390분)
    [3] 1분봉 DF     — 시각 범위, 결측 구간, 가격 스케일
    [4] 30분봉 집계  — 봉 수(정상 13), 구간별 OHLCV 가 1분봉과 일치하는가
    [5] DB 대조      — 이미 적재된 값과 지금 재수집한 값이 같은가

실행
    poetry run python -m app.test.dump_m3_raw                    # 최근 영업일
    poetry run python -m app.test.dump_m3_raw --ymd 20260805
    poetry run python -m app.test.dump_m3_raw --code 114800 --raw # 원시 JSON 전량
"""
import argparse
import json
from datetime import date, datetime, timedelta

import pandas as pd

from app.config.database import dbConn
from app.ext_services.kis.KisEngine import KisEngine
from stock_shared.dao.tradeCandle30mDao import TradeCandle30mDao

EXPECTED_MINUTES = 390      # 09:00~15:29
EXPECTED_BARS = 13          # 30분봉


def sec1_raw(engine: KisEngine, code: str, ymd: str, show_raw: bool):
    print('\n' + '=' * 72)
    print(f'[1] 원시 응답 — {code} {ymd} (커서 153000)')
    print('=' * 72)

    rows = engine._fetch_day_minutes_page(code, ymd, '153000')
    print(f'  output2 행 수 = {len(rows)}   ← 이게 페이지 크기다')
    if not rows:
        print('  ⚠ 빈 응답. 위에 찍힌 rt_cd/msg1 을 확인할 것.')
        return None

    print(f'  필드명: {sorted(rows[0].keys())}')

    if show_raw:
        print('\n  --- 첫 3행 원시 ---')
        for r in rows[:3]:
            print('   ', json.dumps(r, ensure_ascii=False))
        print('  --- 마지막 3행 원시 ---')
        for r in rows[-3:]:
            print('   ', json.dumps(r, ensure_ascii=False))

    hours = [str(r.get('stck_cntg_hour') or '') for r in rows]
    dates = sorted({str(r.get('stck_bsop_date') or '(없음)') for r in rows})
    print(f'\n  시각 범위 : {min(hours)} ~ {max(hours)}  (형식 길이 {len(hours[0])})')
    print(f'  응답 날짜 : {dates}')

    if dates != [ymd] and dates != ['(없음)']:
        print(f'  ⚠ 요청 {ymd} 과 응답 날짜가 다르다 → 이 데이터는 버려진다')
    if len(hours[0]) != 6:
        print(f'  ⚠ 시각 형식이 HHMMSS(6자리)가 아니다 → key 조립이 깨진다')

    # 페이지 크기 판정
    if len(rows) <= 40:
        print(f'\n  ⚠⚠ 페이지가 {len(rows)}건뿐이다. 6회 루프로는 '
              f'{len(rows) * 6}분밖에 못 모은다 (필요 {EXPECTED_MINUTES}분).')
        print(f'      → 하루의 앞쪽(오전) 구간이 통째로 누락된다.')
    return rows


def sec2_paging(engine: KisEngine, code: str, ymd: str):
    print('\n' + '=' * 72)
    print(f'[2] 페이지네이션 추적 — {code} {ymd}')
    print('=' * 72)

    seen = {}
    cursor = '153000'
    for page in range(1, 21):
        rows = engine._fetch_day_minutes_page(code, ymd, cursor)
        if not rows:
            print(f'  page{page:<2} cursor={cursor} → 빈 응답, 중단')
            break

        before = len(seen)
        for r in rows:
            bsop = str(r.get('stck_bsop_date') or ymd)
            key = bsop + str(r.get('stck_cntg_hour') or '')
            if len(key) == 14 and key not in seen:
                seen[key] = r
        added = len(seen) - before

        hours = [str(r.get('stck_cntg_hour') or '') for r in rows]
        oldest = min(hours)
        print(f'  page{page:<2} cursor={cursor} → {len(rows):>3}건 '
              f'({oldest}~{max(hours)}) 신규 {added:>3} 누적 {len(seen):>3}')

        if added == 0:
            print('         진전 없음 → 중단')
            break
        if oldest <= '090000':
            print(f'         09:00 도달 → 완료 (총 {page}페이지)')
            break
        cursor = (datetime.strptime(oldest, '%H%M%S')
                  - timedelta(minutes=1)).strftime('%H%M%S')
    else:
        print('  ⚠ 20페이지를 돌아도 09:00 에 못 닿았다')

    print(f'\n  총 수집 {len(seen)}분 / 기대 {EXPECTED_MINUTES}분')
    if len(seen) < EXPECTED_MINUTES * 0.95:
        print(f'  ⚠ 불완전. 현재 코드는 6페이지에서 끊기므로 실제 백필은 '
              f'이보다 더 적게 받았을 수 있다.')
    return seen


def sec3_1min(engine: KisEngine, code: str, ymd: str, seen: dict):
    print('\n' + '=' * 72)
    print(f'[3] 1분봉 DataFrame')
    print('=' * 72)

    df = engine._minute_rows_to_df(seen)
    if df.empty:
        print('  ⚠ 빈 DataFrame')
        return df

    print(f'  {len(df)}행  {df.index[0]} ~ {df.index[-1]}')
    print(f'  종가 범위 {df["close"].min():,} ~ {df["close"].max():,}')
    print(f'  거래량 합 {int(df["volume"].sum()):,}')

    # 결측 분 구간
    full = pd.date_range(df.index[0], df.index[-1], freq='1min')
    missing = full.difference(df.index)
    if len(missing):
        print(f'  ⚠ 중간 결측 {len(missing)}분 → {[str(m)[11:16] for m in missing[:10]]}')

    # 09:00 로 시작하는가
    if df.index[0].strftime('%H:%M') != '09:00':
        print(f'  ⚠ 첫 봉이 09:00 이 아니라 {df.index[0].strftime("%H:%M")} '
              f'— 오전 구간 누락')

    print('\n  --- 앞 5행 ---')
    print(df.head(5).to_string())
    print('  --- 뒤 5행 ---')
    print(df.tail(5).to_string())
    return df


def sec4_30min(engine: KisEngine, df1m: pd.DataFrame):
    print('\n' + '=' * 72)
    print(f'[4] 30분봉 집계')
    print('=' * 72)

    if df1m.empty:
        print('  1분봉이 비어 있어 생략')
        return None

    df30 = engine.resample_30m(df1m, drop_partial=False)
    print(f'  {len(df30)}봉 / 기대 {EXPECTED_BARS}봉')
    if len(df30) != EXPECTED_BARS:
        print(f'  ⚠ 봉 수 불일치 — 1분봉 구간이 불완전하다는 뜻')
    print()
    print(df30.to_string())

    # 첫 봉을 1분봉으로 직접 재검산
    if len(df30):
        t0 = df30.index[0]
        seg = df1m[(df1m.index >= t0) & (df1m.index < t0 + timedelta(minutes=30))]
        print(f'\n  --- {t0.strftime("%H:%M")} 봉 교차검증 (1분봉 {len(seg)}개) ---')
        exp = {
            'open': seg['open'].iloc[0], 'high': seg['high'].max(),
            'low': seg['low'].min(), 'close': seg['close'].iloc[-1],
            'volume': int(seg['volume'].sum()),
        }
        got = {k: (int(df30.iloc[0][k])) for k in exp}
        ok = all(abs(exp[k] - got[k]) < 1 for k in exp)
        print(f'    1분봉 직접계산 : {exp}')
        print(f'    resample 결과  : {got}')
        print(f'    → {"일치 ✅" if ok else "불일치 ⚠"}')
    return df30


def sec5_db(session, code: str, ymd: str, df30):
    print('\n' + '=' * 72)
    print(f'[5] DB 적재값 대조')
    print('=' * 72)

    d = f'{ymd[:4]}-{ymd[4:6]}-{ymd[6:]}'
    dao = TradeCandle30mDao()
    saved = dao.select_by_range(session, code, f'{d} 00:00:00', f'{d} 23:59:59')
    print(f'  DB 적재 {len(saved)}봉 / 방금 재수집 '
          f'{0 if df30 is None else len(df30)}봉')

    if not saved:
        print('  ⚠ DB 에 이 날짜 데이터가 없다')
        return
    if df30 is None or df30.empty:
        return

    now_map = {t.strftime('%Y-%m-%d %H:%M:%S'): r for t, r in df30.iterrows()}
    diffs = []
    for s in saved:
        k = str(s['datetime'])
        if k not in now_map:
            diffs.append((k, 'DB 에만 있음', '', ''))
            continue
        n = now_map[k]
        for col in ('open', 'high', 'low', 'close', 'volume'):
            a, b = float(s[col] or 0), float(n[col])
            if abs(a - b) > 0.5:
                diffs.append((k, col, a, b))

    only_now = [k for k in now_map if k not in {str(s['datetime']) for s in saved}]
    for k in only_now:
        diffs.append((k, '재수집에만 있음', '', ''))

    if not diffs:
        print('  ✅ DB 값과 재수집 값이 일치')
    else:
        print(f'  ⚠ 불일치 {len(diffs)}건')
        for k, col, a, b in diffs[:15]:
            print(f'    {k}  {col}: DB={a} vs 재수집={b}')


def main():
    ap = argparse.ArgumentParser(description='30분봉 수집 파이프라인 단계별 덤프')
    ap.add_argument('--code', default='237350', help='종목코드')
    ap.add_argument('--ymd', help='조회 일자 YYYYMMDD (기본: 최근 평일)')
    ap.add_argument('--raw', action='store_true', help='원시 JSON 행 출력')
    args = ap.parse_args()

    ymd = args.ymd
    if not ymd:
        d = date.today() - timedelta(days=1)
        while d.weekday() >= 5:
            d -= timedelta(days=1)
        ymd = d.strftime('%Y%m%d')

    engine = KisEngine()
    session = dbConn.get_session()
    try:
        rows = sec1_raw(engine, args.code, ymd, args.raw)
        if rows is None:
            return
        seen = sec2_paging(engine, args.code, ymd)
        df1m = sec3_1min(engine, args.code, ymd, seen)
        df30 = sec4_30min(engine, df1m)
        sec5_db(session, args.code, ymd, df30)

        print('\n' + '=' * 72)
        print('해석 가이드')
        print('=' * 72)
        print('  · [1] 페이지 크기가 30 근처면 → 페이지네이션 하드캡이 원인')
        print('  · [2] 총 수집이 390분 미만이면 → 하루가 잘렸다')
        print('  · [3] 첫 봉이 09:00 이 아니면 → 오전 구간 누락')
        print('  · [4] 교차검증 불일치면 → resample 로직 문제')
        print('  · [5] DB 와 재수집이 다르면 → 백필 당시 데이터가 깨진 것')
    finally:
        session.remove()


if __name__ == '__main__':
    main()
