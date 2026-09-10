"""
FRED(세인트루이스 연방준비은행 경제통계) API 클라이언트.
https://fred.stlouisfed.org/docs/api/fred/series_observations.html
"""
import requests

FRED_OBSERVATIONS_URL = "https://api.stlouisfed.org/fred/series/observations"


class FredEngine:

    def __init__(self, api_key: str):
        self.api_key = api_key

    def get_observations(self, series_id: str, start_date: str, end_date: str = None, sort_order: str = "asc") -> list:
        """
        series_id 의 관측치 목록을 조회합니다.
        start_date/end_date 형식: 'YYYY-MM-DD'.
        반환값: [{date, value, ...}] — value 는 결측치일 경우 '.' 문자열.
        """
        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
            "observation_start": start_date,
            "sort_order": sort_order,
        }
        if end_date:
            params["observation_end"] = end_date

        res = requests.get(FRED_OBSERVATIONS_URL, params=params, timeout=10)
        res.raise_for_status()
        return res.json().get("observations", [])
