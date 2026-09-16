"""
테스트용 배치: trade_shape_scan_stock 전종목의 시가총액(hts_avls)/상장주식수(lstn_stcn)를
KIS 실시간 현재가 조회로 채운다. stock_admin_status.market_cap/listed_shares 갱신.

배경: 매수추천 안정성 필터에 "시가총액 하한" 조건을 추가하기 위해 필요.

수동 실행:
    cd py-project/py-stock-batch && ./.venv/bin/python3 -m app.test.scan_market_cap
"""
import sys
import time

from sqlalchemy import create_engine, text

sys.path.insert(0, '../shared')

from stock_shared.db.database import dbConn
from app.ext_services.kis.KisEngine import KisEngine

DB_URL = 'mysql+pymysql://stock:stock123!!@210.103.60.108:3333/stock'
SLEEP_SEC = 1.5


def main():
    engine = create_engine(DB_URL, pool_pre_ping=True)
    session = dbConn.get_session()

    with engine.begin() as conn:
        rows = conn.execute(text("SELECT DISTINCT coin FROM trade_shape_scan_stock")).fetchall()
    codes = [r[0] for r in rows]
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    if limit:
        codes = codes[:limit]
    print(f"[대상] {len(codes)}종목", flush=True)

    kis_engine = KisEngine()
    ok, fail = 0, 0
    t0 = time.time()

    for idx, code in enumerate(codes):
        try:
            time.sleep(SLEEP_SEC)
            q = kis_engine.kis.stock(code).quote()
            out = q.__data__.get('output', {})
            # hts_avls 는 억원 단위 문자열
            avls_eok = out.get('hts_avls')
            market_cap = float(avls_eok) * 1e8 if avls_eok not in (None, '') else None
            listed_shares = int(out.get('lstn_stcn')) if out.get('lstn_stcn') else None
            rec = {'coin': code, 'market_cap': market_cap, 'listed_shares': listed_shares}
            with engine.begin() as conn:
                conn.execute(text(
                    "UPDATE stock_admin_status SET market_cap=:market_cap, listed_shares=:listed_shares "
                    "WHERE coin=:coin"
                ), rec)
            ok += 1
            if (idx + 1) % 100 == 0 or idx == len(codes) - 1:
                elapsed = time.time() - t0
                eta = (elapsed / (idx + 1)) * (len(codes) - idx - 1) / 60
                print(f"[{idx+1}/{len(codes)}] 성공={ok} 실패={fail} 경과={elapsed/60:.1f}분 예상잔여={eta:.1f}분", flush=True)
        except Exception as e:  # noqa: BLE001
            fail += 1
            print(f"[{idx+1}/{len(codes)}] {code} 실패: {e}", flush=True)
            continue

    print(f"\n[완료] 성공 {ok} / 실패 {fail} (총 {(time.time()-t0)/60:.1f}분)", flush=True)


if __name__ == '__main__':
    main()
