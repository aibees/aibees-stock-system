"""
종목 재무지표(PER·PBR·EPS·BPS·ROE·PEG) 계산 — API(py-naver-stock-theme)와 배치(py-stock-batch)가 같이 쓴다.

출처 두 가지를 짝지어 쓴다.
  1) 주식현재가 시세(FHKST01010100) : PER·PBR·EPS·BPS. PER/PBR 은 "현재가 ÷ 직전 **연간 결산** EPS/BPS".
  2) 국내주식 재무비율(FHKST66430300, 연간 FID_DIV_CLS_CODE=0) : ROE·증가율·부채비율·결산월.
     연간 목록 맨 위에는 진행 중인 해의 누적치(예: 12월 결산사의 202606)가 섞여 온다 → 시세와 기준을 맞추려면
     **확정된 결산 행**을 골라야 한다(삼성전자 2026-10 확인: 결산 202512 의 EPS 6,564 = 시세 EPS 6,564).

이전 계산 오류(2026-10-11 수정):
  - ROE = PBR ÷ PER 로 계산하고 ×100 을 빠뜨려 12% 가 0.12 로 저장됐다 → 재무비율 API 의 roe_val(%) 을 그대로 쓴다.
  - PEG = PER ÷ EPS(원) 로 계산했다 — 틀린 식. PEG = PER ÷ 순이익 증가율(%). 증가율이 0 이하면 의미가 없어 None.
"""
from collections import Counter

RATIO_PATH = "/uapi/domestic-stock/v1/finance/financial-ratio"
RATIO_TR_ID = "FHKST66430300"


def _num(v):
    try:
        if v is None or str(v).strip() == "":
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def fetch_annual_ratios(kis, code: str) -> list:
    """재무비율(연간) 행 목록. 실패하면 [] (호출측은 ROE·PEG 없이 진행)."""
    try:
        resp = kis.request(
            RATIO_PATH, method="GET",
            params={"FID_DIV_CLS_CODE": "0", "fid_cond_mrkt_div_code": "J", "fid_input_iscd": code},
            headers={"tr_id": RATIO_TR_ID, "custtype": "P"},
            appkey_location="header", auth=True,
        )
        j = resp.json()
    except Exception as e:
        print(f"[finance] {code} 재무비율 요청 실패: {e}", flush=True)
        return []
    if j.get("rt_cd") != "0":
        print(f"[finance] {code} 재무비율 rt_cd={j.get('rt_cd')} msg={j.get('msg1')}", flush=True)
        return []
    return j.get("output") or []


def pick_settled_annual(rows: list) -> dict | None:
    """연간 목록에서 확정 결산 행. 결산월 = 목록에서 가장 많이 나오는 월(12월 결산이 아닌 회사 대응)."""
    months = [str(r.get("stac_yymm") or "")[4:6] for r in rows if len(str(r.get("stac_yymm") or "")) == 6]
    if not months:
        return None
    fiscal_month = Counter(months).most_common(1)[0][0]
    for r in rows:   # 최신순
        if str(r.get("stac_yymm") or "")[4:6] == fiscal_month:
            return r
    return None


def build_fundamentals(per, pbr, eps, bps, ratio_row: dict | None) -> dict:
    """화면·저장용 재무지표(숫자). 값이 없으면 None."""
    per, pbr, eps, bps = _num(per), _num(pbr), _num(eps), _num(bps)
    r = ratio_row or {}
    ntin_growth = _num(r.get("ntin_inrt"))
    # 적자 종목은 KIS 가 순이익 증가율을 0.0 으로 준다(계산 불가) → "증가율 0%" 로 보이지 않게 None
    if ntin_growth == 0 and (eps is None or eps <= 0):
        ntin_growth = None
    peg = round(per / ntin_growth, 2) if per and per > 0 and ntin_growth and ntin_growth > 0 else None
    ym = str(r.get("stac_yymm") or "")
    return {
        "per": per, "pbr": pbr, "eps": eps, "bps": bps,
        "roe": _num(r.get("roe_val")),                  # %
        "peg": peg,
        "ntin_growth": ntin_growth,                     # 순이익 증가율 %
        "sales_growth": _num(r.get("grs")),             # 매출액 증가율 %
        "op_growth": _num(r.get("bsop_prfi_inrt")),     # 영업이익 증가율 %
        "debt_ratio": _num(r.get("lblt_rate")),         # 부채비율 %
        "settle_ym": f"{ym[:4]}.{ym[4:6]}" if len(ym) == 6 else None,   # 결산 기준(예: 2025.12)
    }


def to_db_strings(f: dict) -> dict:
    """trade_buy_target_stock 의 eps/per/pbr/roe/peg(String 컬럼) 저장용. 없으면 None(빈 문자열·'0' 대신)."""
    s = lambda v: None if v is None else str(v)
    return {"eps": s(f.get("eps")), "per": s(f.get("per")), "pbr": s(f.get("pbr")),
            "roe": s(f.get("roe")), "peg": s(f.get("peg"))}
