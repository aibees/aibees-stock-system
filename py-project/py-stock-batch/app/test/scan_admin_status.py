"""
테스트용 배치: trade_shape_scan_stock 에 이미 스캔된 전종목의 관리종목/거래정지
상태를 KIS 실시간 현재가 조회(inquire-price, iscd_stat_cls_code/mang_issu_cls_code)
로 확인해 stock_admin_status 에 저장한다.

배경: shape_proba 상위 픽 중 관리종목(급락 후 dead-cat bounce 패턴)이 반복 노출됨.
      shape_* 피처가 "건강한 눌림목 반등"과 "관리종목 폭락 후 반등"을 구분 못하는
      약점이 있어, 관리종목/거래정지/저가주를 사후 필터링하기 위한 상태 데이터가 필요.

주의: 이건 "현재" 상태 스냅샷이다. 7~8월 백테스트에 적용할 땐 "그 당시에도 관리종목
      이었다"는 근사(관리종목 지정은 보통 몇 달 이상 유지됨)로 쓴다 — 완벽히 정확하진
      않지만 실전에서 이 데이터로 걸러도 거의 문제없는 수준일 것으로 판단.

수동 실행:
    cd py-project/py-stock-batch && ./.venv/bin/python3 -m app.test.scan_admin_status
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
            rec = {
                'coin': code,
                'iscd_stat_cls_code': out.get('iscd_stat_cls_code'),
                'mang_issu_cls_code': out.get('mang_issu_cls_code'),
                'temp_stop_yn': out.get('temp_stop_yn'),
                'invt_caful_yn': out.get('invt_caful_yn'),
                'mrkt_warn_cls_code': out.get('mrkt_warn_cls_code'),
                'price': out.get('stck_prpr'),
            }
            with engine.begin() as conn:
                cols = ', '.join(rec.keys())
                vals = ', '.join(f':{k}' for k in rec.keys())
                upd = ', '.join(f'{k}=VALUES({k})' for k in rec.keys() if k != 'coin')
                conn.execute(text(
                    f"INSERT INTO stock_admin_status ({cols}) VALUES ({vals}) "
                    f"ON DUPLICATE KEY UPDATE {upd}"
                ), rec)
            ok += 1
            if (idx + 1) % 50 == 0 or idx == len(codes) - 1:
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
