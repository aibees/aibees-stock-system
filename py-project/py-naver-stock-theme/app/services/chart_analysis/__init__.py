"""일봉 차트 분석(스윙·추세 구조·피보나치·RSI·다이버전스·패턴·엘리엇 파동) — 모듈 단위로 켜고 끈다.

모듈 목록은 MODULES 한 곳에서 관리한다. 어떤 모듈을 계산할지는 공통코드
stock/setting/screen/CHART_ANALYSIS (쉼표 목록, 'N' 이면 전부 끔)가 정하고,
화면은 응답에 들어온 모듈만 레이어 토글로 보여 준다(사용자별 표시 ON/OFF 는 프런트 몫).

각 모듈은 Context 를 받아 JSON 직렬화 가능한 값을 돌려준다. 한 모듈이 실패해도
나머지와 차트 응답은 그대로 나간다.
"""
import logging

import pandas as pd

from app.services.chart_analysis.indicators import atr, rsi
from app.services.chart_analysis.swings import find_swings
from app.services.chart_analysis.structure import analyze_structure
from app.services.chart_analysis.fib import analyze_fib
from app.services.chart_analysis.divergence import analyze_divergence
from app.services.chart_analysis.patterns import analyze_patterns
from app.services.chart_analysis.elliott import analyze_elliott
from app.services.chart_analysis.levels import r


class Context:
    """모듈들이 같이 쓰는 계산(ATR·RSI·스윙)을 한 번만 한다."""

    def __init__(self, full: pd.DataFrame, view_len: int):
        # full: 지표 워밍업용 전체 봉, view: 화면에 그리는 마지막 view_len 봉(스윙·패턴은 이 안에서만 찾는다)
        full = full.reset_index(drop=True)
        self.full = full
        self.atr_full = atr(full['high'].astype(float), full['low'].astype(float), full['close'].astype(float))
        self.rsi_full = rsi(full['close'].astype(float))
        off = max(len(full) - view_len, 0)
        self.view = full.iloc[off:].reset_index(drop=True)
        self.atr = self.atr_full.iloc[off:].reset_index(drop=True)
        self.rsi = self.rsi_full.iloc[off:].reset_index(drop=True)
        self.swings = find_swings(self.view, self.atr)
        self.last_close = float(self.view['close'].iloc[-1])
        self.atr_last = float(self.atr.iloc[-1]) if pd.notna(self.atr.iloc[-1]) else 0.0


def _swing(ctx: Context):
    return [{k: p[k] for k in ('date', 'kind', 'price', 'confirmed')} for p in ctx.swings]


def _rsi(ctx: Context):
    return {
        'period': 14,
        'series': [{'x': d, 'y': r(v) if pd.notna(v) else None} for d, v in zip(ctx.view['ymd'], ctx.rsi)],
        'last': r(ctx.rsi.iloc[-1]) if pd.notna(ctx.rsi.iloc[-1]) else None,
        'atr': r(ctx.atr_last),
    }


MODULES = {
    'swing':      _swing,
    'structure':  lambda ctx: analyze_structure(ctx.swings, ctx.last_close),
    'fib':        lambda ctx: analyze_fib(ctx.swings, ctx.last_close),
    'rsi':        _rsi,
    'divergence': lambda ctx: analyze_divergence(ctx.swings, ctx.rsi.tolist()),
    'pattern':    lambda ctx: analyze_patterns(ctx.view, ctx.swings, ctx.atr_last),
    'elliott':    lambda ctx: analyze_elliott(ctx.view, ctx.atr),
}


def parse_modules(setting: str | None) -> list:
    """공통코드 값 → 켤 모듈 목록. 행이 없으면(None) 전부 켠다."""
    if setting is None:
        return list(MODULES)
    s = setting.strip()
    if s.upper() in ('', 'N', 'OFF'):
        return []
    if s.upper() in ('Y', 'ALL'):
        return list(MODULES)
    return [m for m in (x.strip() for x in s.split(',')) if m in MODULES]


def analyze(full: pd.DataFrame, view_len: int, modules: list) -> dict:
    """full: ymd/open/high/low/close 컬럼의 일봉(오름차순). 반환: {모듈명: 결과}."""
    if not modules or full is None or len(full) < 30:
        return {}
    ctx = Context(full, view_len)
    out = {}
    for name in modules:
        try:
            out[name] = MODULES[name](ctx)
        except Exception as e:
            logging.warning(f"[chart_analysis] {name} 실패: {e}")
    return out
