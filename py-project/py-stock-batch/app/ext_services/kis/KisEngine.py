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

    # ══════════════════════════════════════════════════════════════════
    # 30분봉 (M3 전용)
    #
    #  왜 별도 구현인가 — pykis 로는 안 되는 두 가지:
    #   1) pykis 의 국내 분봉(stock.chart(period=N)) 은 TR FHKST03010200,
    #      즉 "주식당일분봉조회" 다. start/end 가 time 타입만 허용되어
    #      **당일 세션만** 조회된다. 정규장 390분 → 30분봉 13개가 상한이다.
    #      지표에 필요한 250봉(≈20영업일)은 원천적으로 불가능.
    #   2) 게다가 period 인자는 집계가 아니라 샘플링이다.
    #      day_chart.drop_after() 가 `if i % period != 0: continue` 로
    #      1분봉을 30개마다 하나씩 골라낼 뿐이라, high/low/volume 이
    #      30분 구간값이 아니라 그 1분값이다. 그대로 쓰면 지표가 전부 틀어진다.
    #
    #  → 과거분: TR FHKST03010230 (주식일별분봉조회) 로 일자별 1분봉을 긁고
    #    → 당일분: pykis day_chart(period=1) 로 당일 1분봉 전량
    #    양쪽 모두 **직접 30분 resample** 한다.
    # ══════════════════════════════════════════════════════════════════

    BAR_MIN = 30                    # 봉 크기(분)
    MKT_OPEN = "090000"             # 정규장 시작
    MKT_CLOSE = "153000"            # 정규장 종료 (15:20~15:30 종가 단일가 포함)

    # 정규장 09:00~15:29 = 390분. 하루 완전성 판정 기준.
    EXPECTED_MINUTES = 390
    # 이 비율 미만이면 '불완전한 날'로 보고 버린다.
    #   왜 버리는가: 오전 구간이 잘린 채 저장되면 09:00~11:00 봉이 통째로 없는
    #   날이 생기고, 그 상태로 지표를 계산하면 전 구간이 조용히 오염된다.
    #   부분 데이터를 남기는 것보다 그날을 통째로 빼는 쪽이 안전하다.
    MIN_MINUTE_RATIO = 0.90
    # 페이지네이션 상한. 페이지 크기를 모르므로(30건인지 120건인지 응답마다 다름)
    #   횟수를 고정하지 않고 '09:00 에 닿을 때까지' 돈다. 이건 무한루프 방지용 캡.
    #   페이지가 30건이어도 390/30 = 13회면 되므로 20이면 충분하다.
    _MAX_PAGES = 20

    def _fetch_day_minutes_page(self, code: str, ymd: str, hhmmss: str) -> list:
        """주식일별분봉조회 1페이지. hhmmss 이전 방향으로 최대 120건 반환.

        pykis 에 미구현인 TR 이라 원시 호출한다.
        ※ self.kis.fetch() 가 아니라 self.kis.request() + .json() 을 쓴다.
          fetch() 는 응답을 KisDynamicDict 로 감싸 돌려주는데, 그 객체엔 .get() 이
          없어서 dict 로 다루는 순간 AttributeError 가 난다.
          _fetch_daily_mkt 와 동일하게 raw dict 로 받아 처리한다.
        """
        PATH = "/uapi/domestic-stock/v1/quotations/inquire-time-dailychartprice"
        TR_ID = "FHKST03010230"

        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": code,
            "FID_INPUT_DATE_1": ymd,
            "FID_INPUT_HOUR_1": hhmmss,
            "FID_PW_DATA_INCU_YN": "N",
            "FID_FAKE_TICK_INCU_YN": "N",
        }
        try:
            resp = self.kis.request(
                PATH, method="GET", params=params,
                headers={"tr_id": TR_ID, "custtype": "P"},
                appkey_location="header", auth=True,
            )
            j = resp.json()
        except Exception as e:  # noqa: BLE001
            print(f"[_fetch_day_minutes_page] {code} {ymd} {hhmmss} 요청 실패: {e}", flush=True)
            return []

        if j.get("rt_cd") != "0":
            print(f"[_fetch_day_minutes_page] {code} {ymd} rt_cd={j.get('rt_cd')} "
                  f"msg={j.get('msg1')}", flush=True)
            return []

        return [r for r in (j.get("output2") or []) if r.get("stck_cntg_hour")]

    @staticmethod
    def _norm_hhmmss(v) -> str:
        """체결시각을 HHMMSS 6자리로 정규화.

        응답이 'HHMM'(4자리) 또는 앞자리 0이 빠진 'HMMSS'(5자리)로 오는 경우가
        있다. 예전 구현은 길이 14 키만 받아들여서, 형식이 다르면 그날 데이터가
        통째로 조용히 버려졌다.
        """
        s = str(v or "").strip()
        if not s.isdigit():
            return ""
        if len(s) == 4:          # HHMM → HHMM00
            s += "00"
        return s.zfill(6) if len(s) <= 6 else s[:6]

    def fetch_day_minutes(self, code: str, ymd: str, verbose: bool = False) -> pd.DataFrame:
        """특정 일자(YYYYMMDD) 1분봉 전량.

        마감시각(15:30)부터 커서를 내리며 09:00 에 닿을 때까지 반복 호출한다.

        ※ 페이지 크기를 가정하지 않는다.
          이전 구현은 '페이지당 120건'을 전제로 6회만 돌았는데, 실제 응답이
          30건이면 6×30 = 180분밖에 못 받아 **오전 구간이 통째로 누락**됐다.
          그 상태로 resample 하면 하루 13봉이어야 할 게 5~6봉만 생기고,
          그날의 시가가 사라진 채 저장된다. → 종료 조건을 횟수가 아니라
          '09:00 도달'로 바꾸고, 도달 실패 시 경고한다.

        반환: DatetimeIndex + [open, high, low, close, volume]. 없으면 빈 DF.
        """
        seen: dict[str, dict] = {}
        cursor = self.MKT_CLOSE
        reached_open = False
        pages = 0

        for _ in range(self._MAX_PAGES):
            rows = self._fetch_day_minutes_page(code, ymd, cursor)
            pages += 1
            if not rows:
                break

            before = len(seen)
            hours = []
            for r in rows:
                hh = self._norm_hhmmss(r.get("stck_cntg_hour"))
                if not hh:
                    continue
                hours.append(hh)
                # stck_bsop_date 가 비어 오는 응답이 있어 요청 일자로 보정한다.
                bsop = str(r.get("stck_bsop_date") or ymd).strip() or ymd
                key = bsop + hh
                if len(key) == 14 and key not in seen:
                    seen[key] = r

            if not hours or len(seen) == before:
                break                       # 진전 없음 → 무한루프 방지

            oldest = min(hours)
            if oldest <= self.MKT_OPEN:
                reached_open = True
                break
            cursor = (datetime.strptime(oldest, "%H%M%S")
                      - timedelta(minutes=1)).strftime("%H%M%S")

        got = len(seen)
        if verbose or got < self.EXPECTED_MINUTES * self.MIN_MINUTE_RATIO:
            print(f"[fetch_day_minutes] {code} {ymd}: {got}분 수집 "
                  f"({pages}페이지, 09:00도달={reached_open})", flush=True)

        return self._minute_rows_to_df(seen)

    @staticmethod
    def _minute_rows_to_df(seen: dict) -> pd.DataFrame:
        """{YYYYMMDDHHMMSS: row} → 시간 오름차순 1분봉 DataFrame."""
        if not seen:
            return pd.DataFrame()
        keys = sorted(seen)
        recs = [seen[k] for k in keys]
        return pd.DataFrame(
            {
                "open":   [_safe_int(r.get("stck_oprc")) for r in recs],
                "high":   [_safe_int(r.get("stck_hgpr")) for r in recs],
                "low":    [_safe_int(r.get("stck_lwpr")) for r in recs],
                "close":  [_safe_int(r.get("stck_prpr")) for r in recs],
                "volume": [_safe_int(r.get("cntg_vol")) for r in recs],
            },
            index=pd.DatetimeIndex(
                [datetime.strptime(k, "%Y%m%d%H%M%S") for k in keys], name="dt"),
        )

    def fetch_today_minutes(self, code: str) -> pd.DataFrame:
        """당일 1분봉 전량 (pykis day_chart, 1콜).

        과거분 API 와 달리 페이지네이션이 pykis 내부에서 처리된다.
        장중 30분마다 호출해 당일 봉을 통째로 덮어쓰는 용도.
        """
        chart = self.kis.stock(code).chart(period=1)
        bars = getattr(chart, "bars", None) or []
        if not bars:
            return pd.DataFrame()
        return pd.DataFrame(
            {
                "open":   [int(b.open) for b in bars],
                "high":   [int(b.high) for b in bars],
                "low":    [int(b.low) for b in bars],
                "close":  [int(b.close) for b in bars],
                "volume": [int(b.volume) for b in bars],
            },
            index=pd.DatetimeIndex(
                [b.time.replace(tzinfo=None) for b in bars], name="dt"),
        ).sort_index()

    def resample_30m(self, df1m: pd.DataFrame, drop_partial: bool = True,
                     now: datetime | None = None) -> pd.DataFrame:
        """1분봉 → 30분봉 집계.

        origin='start_day' + label/closed='left' → 봉 경계가 09:00 / 09:30 / ...
        로 떨어진다. datetime 은 봉의 **시작 시각**.

        drop_partial: 마지막 봉이 아직 진행 중이면 버린다.
            M3 는 확정봉만으로 지표를 계산한다(repainting 방지).
            판정 기준은 "봉 시작 + 30분 <= 현재시각".
        """
        if df1m is None or df1m.empty:
            return pd.DataFrame()

        out = (
            df1m.resample(f"{self.BAR_MIN}min", origin="start_day",
                          label="left", closed="left")
            .agg({"open": "first", "high": "max", "low": "min",
                  "close": "last", "volume": "sum"})
            .dropna(subset=["open", "close"])
        )

        if drop_partial and not out.empty:
            ref = now or datetime.now()
            edge = timedelta(minutes=self.BAR_MIN)
            # 마감(15:30) 이후의 봉은 이미 확정이므로 시각 비교만으로 충분하다.
            out = out[out.index + edge <= ref]

        return out

    def get_30m_ohlcv(self, code: str, ymd: str, is_today: bool = False,
                      drop_partial: bool = True,
                      require_complete: bool = True) -> pd.DataFrame:
        """일자 단위 30분봉. compute_indicator_df 입력 형식으로 반환.

        Args:
            ymd: 'YYYYMMDD'
            is_today: True 면 당일 API(day_chart), False 면 과거 API(FHKST03010230)
            drop_partial: 진행 중인 마지막 봉 제외 여부
            require_complete: 1분봉이 EXPECTED_MINUTES 의 MIN_MINUTE_RATIO 에
                못 미치면 그날을 통째로 버린다(빈 DF 반환).
                장중(is_today) 은 아직 하루가 안 끝났으므로 자동 면제된다.

        반환: [datetime(str), open, high, low, close, volume] 오름차순.
              데이터 없거나 불완전하면 빈 DataFrame.
        """
        df1m = self.fetch_today_minutes(code) if is_today else self.fetch_day_minutes(code, ymd)
        if df1m.empty:
            return pd.DataFrame()

        # ── 날짜 정합성 ────────────────────────────────────────────────
        # 과거 조회 API 가 요청 날짜를 무시하고 다른 날 데이터를 주는 경우가 있다.
        # 예전엔 이걸 조용히 필터링해 빈 DF 로 넘겼는데, 그러면 "휴장일" 과
        # "API 가 엉뚱한 날을 줬다" 를 구분할 수 없다 → 명시적으로 경고한다.
        day = datetime.strptime(ymd, "%Y%m%d").date()
        other = df1m[df1m.index.date != day]
        if len(other):
            got_days = sorted({str(d) for d in other.index.date})
            print(f"[get_30m_ohlcv] {code} {ymd}: 요청과 다른 날짜 {len(other)}행 "
                  f"섞임 {got_days[:3]} → 제외", flush=True)
            df1m = df1m[df1m.index.date == day]
        if df1m.empty:
            print(f"[get_30m_ohlcv] {code} {ymd}: 요청 날짜 데이터가 0행 → skip",
                  flush=True)
            return pd.DataFrame()

        # ── 완전성 게이트 ──────────────────────────────────────────────
        # 오전이 잘린 하루를 저장하면 그날 시가가 사라지고 봉 수가 들쭉날쭉해진다.
        # 그 상태로 지표를 계산하면 전 구간이 조용히 오염되므로, 애매하면 버린다.
        if require_complete and not is_today:
            need = self.EXPECTED_MINUTES * self.MIN_MINUTE_RATIO
            if len(df1m) < need:
                print(f"[get_30m_ohlcv] {code} {ymd}: 1분봉 {len(df1m)}/"
                      f"{self.EXPECTED_MINUTES}분 (기준 {need:.0f}) → 불완전, 버림",
                      flush=True)
                return pd.DataFrame()
            first_hm = df1m.index[0].strftime("%H:%M")
            if first_hm != "09:00":
                print(f"[get_30m_ohlcv] {code} {ymd}: 첫 1분봉이 {first_hm} "
                      f"(09:00 아님) → 오전 누락, 버림", flush=True)
                return pd.DataFrame()

        df30 = self.resample_30m(df1m, drop_partial=drop_partial)
        if df30.empty:
            return pd.DataFrame()

        return pd.DataFrame({
            "datetime": [t.strftime("%Y-%m-%d %H:%M:%S") for t in df30.index],
            "open":   df30["open"].astype(int).tolist(),
            "high":   df30["high"].astype(int).tolist(),
            "low":    df30["low"].astype(int).tolist(),
            "close":  df30["close"].astype(int).tolist(),
            "volume": df30["volume"].astype("int64").tolist(),
        })
