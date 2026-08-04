from datetime import datetime, timedelta

import pandas as pd
from pykis import PyKis


def _safe_int(v, default=0):
    try:
        return int(float(str(v).strip()))
    except (ValueError, TypeError):
        return default

from app.ext_services.kis.keyLoader import resolve_kis_creds


class KisEngine:
    """KIS 실전투자 전용 엔진. (모의투자 미지원)"""

    def __init__(self, key_path: str = "./spec_keys/kis.key", user_id=None):
        # 1. 자격증명 해석 (실전)
        #    - user_id(인자) 또는 KIS_USER_ID(env) → DB(user_detail) 조회
        #    - 없으면 kis.key 파일 로딩 (하위호환)
        keys = resolve_kis_creds(user_id=user_id, key_path=key_path)

        # 2. 계정 정보 설정
        self.id = keys.get("id")
        self.account = keys.get("account")

        # 3. PyKis (실전). keep_token=True → ~/.pykis/cache 에 토큰 캐시.
        #    컨테이너 내 모든 프로세스(스케줄러 자식 포함)가 같은 캐시를 공유해
        #    토큰은 1회 발급 후 24h 재사용된다(EGW00133 1분1회 제한 회피).
        self.kis = PyKis(
            id=self.id,
            account=self.account,
            appkey=keys.get("app_key"),
            secretkey=keys.get("sec_key"),
            keep_token=True,
        )

    def getOHLCV(self, code: str, start_date: str, end_date: str):
        """일봉 OHLCV 조회 — 통합(UN) 우선, 무데이터/부족 시 KRX(J) fallback.
        요청 [start, end] 구간 그대로 반환.
        반환: [datetime, open, high, low, close, volume] 오름차순."""
        start_ymd = start_date.replace("-", "")
        end_ymd = end_date.replace("-", "")
        seen = self._fetch_daily(code, start_ymd, end_ymd, adj_price=True)
        if not seen:
            return None
        recs = [seen[d] for d in sorted(seen) if start_ymd <= d <= end_ymd]
        if not recs:
            return None
        return pd.DataFrame({
            "datetime": [datetime.strptime(r["stck_bsop_date"], "%Y%m%d").strftime("%Y-%m-%d %H:%M:%S") for r in recs],
            "open":   [_safe_int(r.get("stck_oprc")) for r in recs],
            "high":   [_safe_int(r.get("stck_hgpr")) for r in recs],
            "low":    [_safe_int(r.get("stck_lwpr")) for r in recs],
            "close":  [_safe_int(r.get("stck_clpr")) for r in recs],
            "volume": [_safe_int(r.get("acml_vol")) for r in recs],
        })

    def get_finance_info(self, code: str):
        """재무지표(eps/per/pbr/roe/peg) 조회 — 통합(UN) 우선, KRX(J) fallback."""
        o = self._inquire_price(code)
        if o is None:
            return None
        eps = float(o.get("eps") or 0)
        per = float(o.get("per") or 0)
        pbr = float(o.get("pbr") or 0)
        return {
            'eps': str(eps),
            'per': str(per),
            'pbr': str(pbr),
            'roe': str(round(pbr / per, 2)) if per else '0',
            'peg': str(round(per / eps, 2)) if eps else '0',
        }

    # ──────────────────────────────────────────────────────────────────
    # 현재가 조회 공용 헬퍼 (통합 우선 → KRX fallback).
    #   inquire-price(FHKST01010100). NXT 미대상 종목은 UN 이 비므로 J 로 재조회.
    #   반환: output dict 또는 None.
    # ──────────────────────────────────────────────────────────────────
    def _inquire_price(self, code: str):
        for mkt in ("UN", "J"):
            try:
                resp = self.kis.request(
                    "/uapi/domestic-stock/v1/quotations/inquire-price",
                    method="GET",
                    params={"FID_COND_MRKT_DIV_CODE": mkt, "FID_INPUT_ISCD": code},
                    headers={"tr_id": "FHKST01010100", "custtype": "P"},
                    appkey_location="header", auth=True,
                )
                j = resp.json()
            except Exception as e:
                print(f"[_inquire_price] {code}({mkt}) 요청 실패: {e}", flush=True)
                continue
            if j.get("rt_cd") != "0":
                print(f"[_inquire_price] {code}({mkt}) rt_cd={j.get('rt_cd')} msg={j.get('msg1')}", flush=True)
                continue
            o = j.get("output") or {}
            if o.get("stck_prpr"):   # 현재가 존재 = 유효 응답
                if mkt == "J":
                    print(f"[_inquire_price] {code} UN 무데이터 → KRX(J) fallback", flush=True)
                return o
        return None

    # 수집 결과의 마지막 영업일이 요청 종료일보다 이만큼 뒤처지면 '최신 데이터 누락'으로 간주.
    _STALE_GAP_DAYS = 10

    def _latest_gap(self, seen: dict, end_ymd: str) -> int:
        """수집된 마지막 영업일과 요청 종료일의 일수 차이. 데이터 없으면 매우 큰 값."""
        if not seen:
            return 10 ** 6
        return (datetime.strptime(end_ymd, "%Y%m%d") - datetime.strptime(max(seen), "%Y%m%d")).days

    # ──────────────────────────────────────────────────────────────────
    # 일봉 REST 페이지네이션 공용 헬퍼 (통합 우선 → 부족/누락 시 KRX fallback).
    #   inquire-daily-itemchartprice(FHKST03010100).
    #   FID_COND_MRKT_DIV_CODE: 'UN'(KRX+NXT 통합) 우선. 단, NXT 미대상(KRX 전용)이거나
    #   NXT 편입이 늦어 통합 일봉 히스토리가 짧거나(거래일 부족),
    #   최신 구간이 누락되면 'J'(KRX)로 재조회한다.
    #   ※ 보충 방식: UN 결과는 유지하고 '없는 영업일'만 J 로 채운다(UN 우선).
    #     UN(통합, NXT 시간외 포함)과 J(KRX 정규장)는 같은 날 종가가 다를 수 있어
    #     한 시계열에 두 기준이 섞일 수 있다. 지표 연속성이 중요하면 J 단일 기준으로
    #     통일하는 편이 안전하다.
    #   1회 100행 제한 → 날짜 윈도우로 floor_ymd 까지 수집.
    #   반환: {영업일자(YYYYMMDD) -> output2 row} (중복 제거). getOHLCV / get_daily_ohlcv 공용.
    # ──────────────────────────────────────────────────────────────────
    def _fetch_daily(self, code: str, floor_ymd: str, end_ymd: str,
                     adj_price: bool = True, min_rows: int = 0) -> dict:
        # UN(통합) 우선.
        seen = self._fetch_daily_mkt(code, floor_ymd, end_ymd, "UN", adj_price, min_rows)
        gap = self._latest_gap(seen, end_ymd)

        # fallback 사유: 무데이터(KRX전용) / 거래일 부족(NXT 편입 늦음) / 최신 데이터 누락
        if not seen:
            reason = "무데이터"
        elif len(seen) < min_rows:
            reason = f"거래일 부족({len(seen)}행)"
        elif gap > self._STALE_GAP_DAYS:
            reason = f"최신 누락(마지막={max(seen)} {gap}일 차)"
        else:
            reason = None

        if reason:
            seen_j = self._fetch_daily_mkt(code, floor_ymd, end_ymd, "J", adj_price, min_rows)
            if not seen:
                # UN 이 아예 없으면 J 로 전량 대체
                if seen_j:
                    print(f"[_fetch_daily] {code} UN {reason} → KRX(J) 전량 대체 "
                          f"({len(seen_j)}행, 마지막={max(seen_j)})", flush=True)
                seen = seen_j
            else:
                # UN 결과는 그대로 두고 '누락된 영업일'만 J 로 채운다(UN 우선).
                added = [d for d in seen_j if d not in seen]
                for d in added:
                    seen[d] = seen_j[d]
                if added:
                    print(f"[_fetch_daily] {code} UN {reason} → KRX(J) 누락분 {len(added)}행 보충 "
                          f"({min(added)}~{max(added)}), 합계 {len(seen)}행 마지막={max(seen)}", flush=True)
            gap = self._latest_gap(seen, end_ymd)

        # fallback 이후에도 최신 구간이 비면 경고
        if seen and gap > self._STALE_GAP_DAYS:
            print(f"[_fetch_daily] {code} 최신 데이터 누락 의심: 마지막={max(seen)} "
                  f"요청종료={end_ymd} ({gap}일 차)", flush=True)
        return seen

    # 1회 호출 한도(100건) 이내가 되도록 조회 윈도우를 캘린더일로 제한한다.
    # 130 캘린더일 ≒ 90 거래일 < 100건. (공휴일/연휴 편차를 감안한 여유값)
    _WINDOW_DAYS = 130

    def _fetch_daily_mkt(self, code: str, floor_ymd: str, end_ymd: str, mkt: str,
                         adj_price: bool = True, min_rows: int = 0) -> dict:
        """[start, end] 를 100건 이하 윈도우로 잘라 최신→과거 방향으로 수집.
        ※ 이 API 는 1회 최대 100건이라, DATE_1 을 먼 과거로 고정한 채 DATE_2 만 옮기면
          서버가 어느 쪽 100건을 잘라주는지에 따라 최신 구간이 통째로 누락될 수 있다.
          → 항상 DATE_1/DATE_2 를 함께 옮겨 윈도우 자체를 100건 이하로 유지한다."""
        PATH = "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"
        TR_ID = "FHKST03010100"

        floor_dt = datetime.strptime(floor_ymd, "%Y%m%d")
        cur_end = end_ymd
        seen: dict[str, dict] = {}
        guard = 0
        while cur_end >= floor_ymd and guard < 30:
            guard += 1
            cur_end_dt = datetime.strptime(cur_end, "%Y%m%d")
            win_start_dt = max(floor_dt, cur_end_dt - timedelta(days=self._WINDOW_DAYS))
            win_start = win_start_dt.strftime("%Y%m%d")

            params = {
                "FID_COND_MRKT_DIV_CODE": mkt,           # J: KRX, NX: NXT, UN: 통합
                "FID_INPUT_ISCD": code,
                "FID_INPUT_DATE_1": win_start,           # 윈도우 시작(100건 이내)
                "FID_INPUT_DATE_2": cur_end,             # 윈도우 종료
                "FID_PERIOD_DIV_CODE": "D",              # D:일 W:주 M:월 Y:년
                "FID_ORG_ADJ_PRC": "0" if adj_price else "1",  # 0:수정주가 1:원주가
            }
            try:
                resp = self.kis.request(
                    PATH, method="GET", params=params,
                    headers={"tr_id": TR_ID, "custtype": "P"},
                    appkey_location="header", auth=True,
                )
                j = resp.json()
            except Exception as e:
                print(f"[_fetch_daily_mkt] {code}({mkt}) 요청 실패: {e}", flush=True)
                break

            if j.get("rt_cd") != "0":
                print(f"[_fetch_daily_mkt] {code}({mkt}) rt_cd={j.get('rt_cd')} msg={j.get('msg1')}", flush=True)
                break

            rows = [r for r in (j.get("output2") or []) if r.get("stck_bsop_date")]
            for r in rows:
                seen[r["stck_bsop_date"]] = r

            # 윈도우 시작이 floor 에 닿았으면 종료(+최소 행수 확보 시)
            if win_start <= floor_ymd:
                break
            if len(seen) >= min_rows and min_rows > 0:
                break
            # 다음 윈도우: 이번 윈도우 시작 하루 전까지
            cur_end = (win_start_dt - timedelta(days=1)).strftime("%Y%m%d")

        return seen

    # ──────────────────────────────────────────────────────────────────
    # 국내주식기간별시세(일/주/월/년) — inquire-daily-itemchartprice
    #   TR_ID: FHKST03010100
    #   매수추천배치(StockBuyCheckJob) 의 일봉 조회용.
    #   pykis 의 인증 토큰/도메인/rate-limit 을 그대로 재사용(self.kis.request).
    #   반환 형식은 getOHLCV 와 동일: [datetime, open, high, low, close, volume] 오름차순.
    #   ※ 이 API 는 1회 최대 100행 → 날짜 윈도우 페이지네이션으로 start_date 까지 수집.
    # ──────────────────────────────────────────────────────────────────
    def get_daily_ohlcv(self, code: str, start_date: str, end_date: str,
                        adj_price: bool = True, min_days: int = 250):
        """일봉 OHLCV 조회. 최소 min_days(기본 250) '거래일'을 보장한다.
        - start_date 는 하한 힌트. 그 구간이 min_days 미만이면 그 이전까지 더 조회해 최근 min_days 보장.
        - KIS API 1회 100행 제한 → 날짜 윈도우 페이지네이션."""
        start_ymd = start_date.replace("-", "")
        end_dt = datetime.strptime(end_date.replace("-", ""), "%Y%m%d")
        # 조회 하한: start_date 와 (min_days 거래일 확보용 여유 캘린더일=min_days*2) 중 더 이른 날
        floor_dt = min(datetime.strptime(start_ymd, "%Y%m%d"), end_dt - timedelta(days=min_days * 2))
        floor_ymd = floor_dt.strftime("%Y%m%d")

        seen = self._fetch_daily(code, floor_ymd, end_dt.strftime("%Y%m%d"),
                                 adj_price=adj_price, min_rows=min_days)
        if not seen:
            return None

        all_dates = sorted(seen)                                   # 오름차순
        in_range = [d for d in all_dates if d >= start_ymd]
        # 요청 구간이 min_days 이상이면 그대로, 미만이면 최근 min_days 거래일 사용
        keep = in_range if len(in_range) >= min_days else all_dates[-min_days:]
        recs = [seen[d] for d in keep]
        # UN→J fallback 후에도 거래일 부족이면 실패로 간주(None)
        if len(recs) < min_days:
            print(f"[get_daily_ohlcv] {code} 거래일 부족: {len(recs)}일 (요청 최소 {min_days}일) → 실패 처리", flush=True)
            return None

        df = pd.DataFrame({
            "datetime": [datetime.strptime(r["stck_bsop_date"], "%Y%m%d").strftime("%Y-%m-%d %H:%M:%S") for r in recs],
            "open":   [_safe_int(r.get("stck_oprc")) for r in recs],
            "high":   [_safe_int(r.get("stck_hgpr")) for r in recs],
            "low":    [_safe_int(r.get("stck_lwpr")) for r in recs],
            "close":  [_safe_int(r.get("stck_clpr")) for r in recs],
            "volume": [_safe_int(r.get("acml_vol")) for r in recs],
        })
        return df
