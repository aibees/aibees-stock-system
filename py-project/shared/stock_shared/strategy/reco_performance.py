"""매수추천 이후 성과 분석.

"이 종목은 추천 이후 최고 몇 %까지 올랐나"를 추천 건별로 계산한다.
같은 종목이 여러 번 추천됐으면 **추천일마다 별도 행**으로 나온다
(추천 시점이 다르면 기준가도 결과도 다르므로 합치면 의미가 없다).

산출 항목
  · 최고/최저 : 추천일 이후 구간의 high 최대 / low 최소 + 각 도달일·경과봉수
  · 현재      : 구간 마지막 종가와 수익률
  · 변곡점    : ZigZag 스윙 (임계 % 이상 반전한 지점만)

ZigZag 를 쓰는 이유
  단순 최고/최저만 보면 "언제 올랐다 언제 빠졌는지"를 알 수 없다.
  매일의 자잘한 등락을 전부 그리면 노이즈에 묻히므로, **직전 극값 대비
  임계 % 이상 반대로 움직인 경우만** 스윙으로 인정해 흐름만 남긴다.
"""
from decimal import Decimal

from sqlalchemy import text


def _f(v, default=0.0):
    if v is None:
        return default
    if isinstance(v, Decimal):
        return float(v)
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _pct(base: float, v: float) -> float:
    return round((v - base) / base * 100, 2) if base else 0.0


def zigzag(rows: list, threshold_pct: float = 5.0) -> list:
    """ZigZag 변곡점 추출. **종가 기준**.

    rows: [{'date','close', ...}, ...] 날짜 오름차순.
    threshold_pct: 직전 극값 대비 이 % 이상 반전해야 스윙으로 인정.

    반환: [{'date','kind':'high'|'low','price','pct_from_prev'}, ...]

    ※ high/low(장중 고저)가 아니라 종가를 쓴다.
      일봉의 high-low 폭이 임계보다 큰 종목(변동성 큰 소형주는 하루 20~30%)에서는
      high/low 기준이면 **매 봉마다 스윙이 잡혀** 같은 날 고점·저점이 동시에
      기록되고 노이즈만 남는다. 실제로 SK이터닉스(475150)를 임계 10%로 돌렸을 때
      19봉에서 17개가 나왔다. 흐름을 보려는 목적에 맞지 않는다.
      종가 기준이면 하루 안의 흔들림이 제거되어 추세 전환만 남는다.
      (구간 최고/최저는 별도로 high/low 기준을 유지한다 — 그건 "얼마까지
       갔었나"를 묻는 값이라 장중 고저가 맞다)
    """
    if len(rows) < 2 or threshold_pct <= 0:
        return []

    th = threshold_pct / 100.0
    pivots = []

    direction = 0                      # 1=상승(고점 탐색), -1=하락(저점 탐색), 0=미정
    start_p = rows[0]['close']         # 시작점(추천일 종가)
    ext_i, ext_p = 0, start_p

    def _push(idx, kind, price):
        # 첫 스윙은 비교할 직전 극값이 없으므로 시작점(추천일 종가) 대비로 본다.
        prev = pivots[-1]['price'] if pivots else start_p
        pivots.append({
            'date': rows[idx]['date'],
            'kind': kind,
            'price': round(price, 2),
            'pct_from_prev': _pct(prev, price),
        })

    for i in range(1, len(rows)):
        c = rows[i]['close']
        if c <= 0 or ext_p <= 0:
            continue

        if direction == 0:
            # 방향 미정 — 시작점 대비 임계를 먼저 넘는 쪽으로 추세를 확정한다.
            #   ※ 여기를 갱신 분기와 합치면(elif 체인) c>ext_p / c<ext_p 가
            #     항상 먼저 걸려 확정 분기에 영원히 도달하지 못한다.
            if (c - start_p) / start_p >= th:
                direction, ext_p, ext_i = 1, c, i
            elif (start_p - c) / start_p >= th:
                direction, ext_p, ext_i = -1, c, i
            continue

        if direction > 0:
            if c > ext_p:                          # 고점 갱신
                ext_p, ext_i = c, i
            elif (ext_p - c) / ext_p >= th:        # 고점 확정 → 하락 전환
                _push(ext_i, 'high', ext_p)
                direction, ext_p, ext_i = -1, c, i
        else:
            if c < ext_p:                          # 저점 갱신
                ext_p, ext_i = c, i
            elif (c - ext_p) / ext_p >= th:        # 저점 확정 → 상승 전환
                _push(ext_i, 'low', ext_p)
                direction, ext_p, ext_i = 1, c, i

    # 마지막 미확정 극값(진행 중 구간)도 잠정 스윙으로 포함
    if direction != 0:
        _push(ext_i, 'high' if direction > 0 else 'low', ext_p)

    return pivots


class RecoPerformanceAnalyzer:
    """추천 건별 성과 분석. 캔들은 한 번에 읽어 종목별로 나눠 쓴다."""

    def __init__(self, session):
        self.session = session

    # ── 데이터 로딩 ────────────────────────────────────────────────
    def _load_recos(self, from_ymd: str, to_ymd: str = None) -> list:
        sql = ("SELECT ymd, stock_code, stock_name, close, rate, score, rank_no "
               "FROM trade_buy_target_stock WHERE ymd >= :s")
        p = {'s': from_ymd}
        if to_ymd:
            sql += " AND ymd <= :e"
            p['e'] = to_ymd
        sql += " ORDER BY ymd DESC, rank_no"
        return [dict(r) for r in self.session.execute(text(sql), p).mappings().all()]

    def _load_candles(self, codes: list, from_dt: str) -> dict:
        """{coin: [{'date','open','high','low','close'}, ...]} 날짜 오름차순.

        종목마다 따로 조회하면 364회 왕복이라 한 번에 읽는다.
        """
        if not codes:
            return {}
        # IN 절 파라미터 바인딩
        keys = {f'c{i}': c for i, c in enumerate(codes)}
        placeholders = ", ".join(f":{k}" for k in keys)
        sql = (f"SELECT coin, datetime, open, high, low, close "
               f"FROM trade_candle_data "
               f"WHERE coin IN ({placeholders}) AND datetime >= :from_dt "
               f"ORDER BY coin, datetime")
        params = dict(keys, from_dt=from_dt)

        out = {}
        for r in self.session.execute(text(sql), params).mappings().all():
            out.setdefault(r['coin'], []).append({
                'date': str(r['datetime'])[:10],
                'open': _f(r['open']), 'high': _f(r['high']),
                'low': _f(r['low']), 'close': _f(r['close']),
            })
        return out

    # ── 분석 ───────────────────────────────────────────────────────
    def run(self, from_ymd: str, to_ymd: str = None,
            horizon_days: int = 0, zigzag_pct: float = 5.0,
            include_pivots: bool = True) -> dict:
        """
        from_ymd/to_ymd : 추천일 범위 (YYYYMMDD)
        horizon_days    : 추천일 이후 관측할 **거래일 수**. 0 이면 데이터 끝까지.
        zigzag_pct      : 변곡점 임계 %. 0 이면 변곡점 계산 안 함.
        """
        recos = self._load_recos(from_ymd, to_ymd)
        if not recos:
            return {'ok': False, 'message': f'{from_ymd} 이후 추천 이력이 없습니다.',
                    'rows': [], 'summary': None}

        codes = sorted({r['stock_code'] for r in recos})
        # 가장 이른 추천일부터의 캔들만 있으면 된다
        min_ymd = min(r['ymd'] for r in recos)
        from_dt = f"{min_ymd[:4]}-{min_ymd[4:6]}-{min_ymd[6:8]} 00:00:00"
        candles = self._load_candles(codes, from_dt)

        rows = []
        for reco in recos:
            row = self._analyze_one(reco, candles.get(reco['stock_code'], []),
                                    horizon_days, zigzag_pct, include_pivots)
            if row:
                rows.append(row)

        return {
            'ok': True,
            'params': {'from_ymd': from_ymd, 'to_ymd': to_ymd,
                       'horizon_days': horizon_days, 'zigzag_pct': zigzag_pct},
            'summary': self._summarize(rows),
            'rows': rows,
        }

    def _analyze_one(self, reco: dict, series: list, horizon_days: int,
                     zigzag_pct: float, include_pivots: bool):
        ymd = reco['ymd']
        d = f"{ymd[:4]}-{ymd[4:6]}-{ymd[6:8]}"

        # 추천일 **다음** 거래일부터가 관측 구간.
        #   추천은 그날 장 마감 후 나오므로 당일 고가는 이미 지나간 값이다.
        after = [c for c in series if c['date'] > d]
        if horizon_days > 0:
            after = after[:horizon_days]
        if not after:
            return None

        base = _f(reco['close'])
        if base <= 0:
            return None

        hi_bar = max(after, key=lambda c: c['high'])
        lo_bar = min(after, key=lambda c: c['low'])
        last = after[-1]

        # 다음 거래일 시가 — 실제로 살 수 있었던 가격(시뮬의 next_open 과 동일 기준)
        next_open = after[0]['open']

        out = {
            'ymd': ymd,
            'reco_date': d,
            'stock_code': reco['stock_code'],
            'stock_name': reco['stock_name'],
            'score': _f(reco['score'], None) if reco['score'] is not None else None,
            'rank_no': reco['rank_no'],
            'base_close': round(base, 2),
            'next_open': round(next_open, 2),
            'next_open_gap_pct': _pct(base, next_open),

            'max_high': round(hi_bar['high'], 2),
            'max_high_date': hi_bar['date'],
            'max_high_pct': _pct(base, hi_bar['high']),
            'max_high_bars': after.index(hi_bar) + 1,

            'min_low': round(lo_bar['low'], 2),
            'min_low_date': lo_bar['date'],
            'min_low_pct': _pct(base, lo_bar['low']),
            'min_low_bars': after.index(lo_bar) + 1,

            'last_close': round(last['close'], 2),
            'last_date': last['date'],
            'last_pct': _pct(base, last['close']),
            'observed_bars': len(after),
            # 고점이 저점보다 먼저 왔는지 — 먼저 오르고 빠졌나, 빠졌다 올랐나
            'high_first': hi_bar['date'] <= lo_bar['date'],
        }

        if include_pivots and zigzag_pct > 0:
            # 추천일 봉을 시작점으로 포함해야 첫 스윙의 기준이 잡힌다
            seed = [c for c in series if c['date'] == d]
            pv = zigzag(seed + after, zigzag_pct)
            for p in pv:
                p['pct_from_base'] = _pct(base, p['price'])
            out['pivots'] = pv
            out['pivot_count'] = len(pv)
        return out

    @staticmethod
    def _summarize(rows: list) -> dict:
        if not rows:
            return {'count': 0}
        n = len(rows)
        highs = [r['max_high_pct'] for r in rows]
        lasts = [r['last_pct'] for r in rows]
        return {
            'count': n,
            'codes': len({r['stock_code'] for r in rows}),
            'avg_max_high_pct': round(sum(highs) / n, 2),
            'avg_min_low_pct': round(sum(r['min_low_pct'] for r in rows) / n, 2),
            'avg_last_pct': round(sum(lasts) / n, 2),
            'best': max(rows, key=lambda r: r['max_high_pct'])['max_high_pct'],
            'worst': min(rows, key=lambda r: r['min_low_pct'])['min_low_pct'],
            # 추천 이후 한 번이라도 +N% 를 찍은 비율 — 익절 목표 설정에 참고
            'hit_5': round(sum(1 for h in highs if h >= 5) / n * 100, 1),
            'hit_10': round(sum(1 for h in highs if h >= 10) / n * 100, 1),
            'hit_20': round(sum(1 for h in highs if h >= 20) / n * 100, 1),
            'hit_30': round(sum(1 for h in highs if h >= 30) / n * 100, 1),
        }


def analyze(session, **kwargs) -> dict:
    return RecoPerformanceAnalyzer(session).run(**kwargs)
