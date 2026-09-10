"""
'세계주요지표' 탭 데이터 서비스.
FRED API에서 가져오는 지표를 중분류(카테고리)별로 묶어 제공한다.
"""
import time
from datetime import datetime, timedelta

from app.domains.dao.masterCodesDao import MasterCodesDao
from app.ext_services.fred.FredEngine import FredEngine

# FRED 시리즈 ID : 국채(https://fred.stlouisfed.org/categories/115), 유가(https://fred.stlouisfed.org/categories/32255)
INDICATOR_GROUPS = [
    {
        "category": "treasury",
        "category_label": "미국 국채 금리",
        "unit": "percent",
        "metric_word": "금리",
        "series": [
            {"series_id": "DGS6MO", "label": "6개월 국채"},
            {"series_id": "DGS2", "label": "2년 국채"},
            {"series_id": "DGS10", "label": "10년 국채"},
            {"series_id": "DGS30", "label": "30년 국채"},
        ],
    },
    {
        "category": "oil",
        "category_label": "국제 유가",
        "unit": "usd",
        "metric_word": "가격",
        "series": [
            {"series_id": "DCOILWTICO", "label": "WTI"},
            {"series_id": "DCOILBRENTEU", "label": "브렌트유"},
        ],
    },
]

_UNIT_FORMAT = {
    "percent": {"value": "{:.2f}%", "change": "{:+.2f}%p"},
    "usd": {"value": "${:.2f}", "change": "{:+.2f}달러"},
}

_RECENT_DAYS = 60
# FRED 데이터는 하루 한 번 갱신되므로, 탭을 열 때마다 매번 외부 API를 두드릴 필요가 없다.
_CACHE_TTL_SECONDS = 1800
_cache = {}  # {series_id: (fetched_at, payload)}


class WorldIndicatorService:

    def __init__(self):
        self._masterCodesDao = MasterCodesDao()

    def get_world_indicators(self, session) -> list:
        fred = FredEngine(self._get_fred_api_key(session))
        start_date = (datetime.today() - timedelta(days=120)).strftime("%Y-%m-%d")

        return [
            {
                "category": group["category"],
                "category_label": group["category_label"],
                "unit": group["unit"],
                "metric_word": group["metric_word"],
                "items": [
                    self._build_indicator(fred, meta, start_date, group["unit"], group["metric_word"])
                    for meta in group["series"]
                ],
            }
            for group in INDICATOR_GROUPS
        ]

    # ── 내부 ──────────────────────────────────────────────

    def _get_fred_api_key(self, session) -> str:
        rows = self._masterCodesDao.select_master_code(session, {
            "system": "stock",
            "source": "setting",
            "category": "api-key",
        })
        for row in rows:
            if row["code"] == "FRED":
                return row["desc"]
        raise ValueError("FRED API 키를 찾을 수 없습니다 (master_codes: stock/setting/api-key/FRED).")

    def _build_indicator(self, fred: FredEngine, meta: dict, start_date: str, unit: str, metric_word: str) -> dict:
        series_id = meta["series_id"]

        now = time.time()
        cached = _cache.get(series_id)
        if cached and now - cached[0] < _CACHE_TTL_SECONDS:
            return cached[1]

        observations = fred.get_observations(series_id, start_date)
        points = [
            {"date": o["date"], "value": float(o["value"])}
            for o in observations
            if o.get("value") not in (None, ".")
        ][-_RECENT_DAYS:]

        payload = {
            "series_id": series_id,
            "label": meta["label"],
            "observations": points,
            **self._summarize(meta["label"], metric_word, points, unit),
        }
        _cache[series_id] = (now, payload)
        return payload

    @staticmethod
    def _summarize(label: str, metric_word: str, points: list, unit: str) -> dict:
        fmt = _UNIT_FORMAT[unit]

        if not points:
            return {
                "latest_value": None,
                "latest_date": None,
                "change": None,
                "summary": f"{label} {metric_word} 데이터를 가져오지 못했습니다.",
            }

        latest = points[-1]
        prev = points[-2] if len(points) > 1 else None
        change = round(latest["value"] - prev["value"], 2) if prev else None
        values = [p["value"] for p in points]

        change_str = f" · 전일대비 {fmt['change'].format(change)}" if change is not None else ""

        summary = (
            f"{label} {metric_word} {fmt['value'].format(latest['value'])} ({latest['date']}){change_str}"
            f" · 최근 {len(points)}일 범위 {fmt['value'].format(min(values))}~{fmt['value'].format(max(values))}"
        )

        return {
            "latest_value": latest["value"],
            "latest_date": latest["date"],
            "change": change,
            "summary": summary,
        }
