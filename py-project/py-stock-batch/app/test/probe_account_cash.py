"""
예수금 / 매수가능금액 대조 프로브 (조회 전용 — 주문 없음).

목적:
    user_wallet.user_balance 에 들어가는 값은 지금 broker.account_cash() 가
    만든다. 그 구현은 매수가능조회(inquire-psbl-order)를 **삼성전자(005930)**
    로 던진 nrcvb_buy_amt 다(broker.py CASH_REF_SYMBOL). 매수가능조회는 PDNO 가
    필수라 대표종목을 끼워 넣은 것인데, 이 값이 정말 종목과 무관한지 확인되지
    않은 채 계좌 잔액처럼 쓰이고 있다.

    이 스크립트는 같은 계좌에 대해
      (A) 잔고조회(inquire-balance)   — 종목 인자 없는 계좌 단위 현금
      (B) 매수가능조회(inquire-psbl-order) — 종목별로 반복
    를 나란히 찍어, 종목에 따라 값이 갈리는지와 MTS 실계좌와 맞는지를 대조한다.

    [2026-09-30 실계좌 대조 결과]
      · ord_psbl_cash(주문가능현금) · nrcvb_buy_amt(미수없는매수금액) 모두 **종목 무관**.
        → CASH_REF_SYMBOL(삼성전자) 프록시 조회는 유효하다.
      · 다만 두 값은 증거금징수율·미체결 주문 때문에 **서로 다르다**.
        → user_wallet: user_balance=매수가능금액 / deposit=예수금 으로 분리 적재한다.
    이후로는 회귀 확인용이다 — 위 두 전제가 깨지지 않았는지 주기적으로 돌려보면 된다.

    ※ 모두 GET 조회다. 주문/정정/취소는 하지 않는다.

사용법(py-stock-batch 프로젝트 루트에서):
    poetry run python -m app.test.probe_account_cash --user-id 1
    poetry run python -m app.test.probe_account_cash --user-id 1 --codes 005930,000660,042700
    poetry run python -m app.test.probe_account_cash --user-id 1 --no-db

    --codes 미지정 시: 삼성전자 + 현재 보유종목 + 기본 비교군으로 자동 구성.
    실제로 매수 후보에 오르는 종목들을 --codes 로 넘겨야 의미가 가장 크다.

MTS 대조 포인트:
    '예수금'        → dnca_tot_amt
    'D+2 예수금'    → prvs_rcdl_excc_amt   ← 보통 이 값이 실제 가용현금
    '총평가금액'    → tot_evlu_amt
    '순자산'        → nass_amt
    '주문가능금액'  → 종목별로 다름. (B) 표에서 확인
"""
from __future__ import annotations

import argparse
import os
from decimal import Decimal

from app.ext_services.kis.KisEngine import KisEngine

# 종목별 편차를 보기 위한 기본 비교군(증거금 등급이 서로 다를 법한 대형/중형주).
# 어디까지나 예시다 — 실제 매수 후보로 바꿔 쓰는 편이 정확하다.
DEFAULT_EXTRA_CODES = ["005930", "000660", "035720", "042700"]

# broker.py 가 계좌 잔액 프록시로 쓰는 종목. 대조 기준점.
REF_CODE = "005930"

# (A) 잔고조회 output2 에서 뽑아볼 현금 관련 필드.
CASH_FIELDS = [
    ("dnca_tot_amt",        "예수금총금액",         "D+0. 미결제분 포함 → 실제 가용액보다 큼"),
    ("nxdy_excc_amt",       "익일정산금액",         "D+1"),
    ("prvs_rcdl_excc_amt",  "가수도정산금액",       "D+2 ★ 보통 이게 '진짜 예수금'"),
    ("thdt_buy_amt",        "금일매수금액",         ""),
    ("thdt_sll_amt",        "금일매도금액",         ""),
    ("scts_evlu_amt",       "유가증권평가금액",     "보유주식 평가"),
    ("evlu_amt_smtl_amt",   "평가금액합계금액",     ""),
    ("tot_evlu_amt",        "총평가금액",           "유가증권 + D+2예수금"),
    ("nass_amt",            "순자산금액",           ""),
    ("evlu_pfls_smtl_amt",  "평가손익합계금액",     ""),
]

# (B) 매수가능조회 output 에서 뽑아볼 필드.
PSBL_FIELDS = [
    ("ord_psbl_cash",   "주문가능현금",       "★ user_wallet.deposit (화면 '예수금')"),
    ("nrcvb_buy_amt",   "미수없는매수금액",   "★ user_wallet.user_balance (매수 판단 기준)"),
    ("nrcvb_buy_qty",   "미수없는매수수량",   "종목 가격에 종속 — 당연히 갈림"),
    ("max_buy_amt",     "최대매수금액",       "미수 포함 → 증거금율 반영"),
    ("max_buy_qty",     "최대매수수량",       ""),
    ("ruse_psbl_amt",   "재사용가능금액",     ""),
    ("ord_psbl_sbst",   "주문가능대용",       "대용증권 인정분"),
]


def _dec(v) -> Decimal:
    try:
        return Decimal(str(v).strip() or "0")
    except Exception:  # noqa: BLE001
        return Decimal(0)


def _won(v) -> str:
    """원화 천단위 포맷."""
    d = _dec(v)
    return f"{d:>18,.0f}"


def _rule(title: str = "", width: int = 86):
    if title:
        print(f"\n{'─' * 4} {title} {'─' * max(0, width - len(title) - 6)}")
    else:
        print("─" * width)


# ──────────────────────────────────────────────────────────────────
# (A) 잔고조회 — inquire-balance / TTTC8434R
#     종목 인자 없음. output1=보유종목, output2=계좌 요약(현금 포함).
# ──────────────────────────────────────────────────────────────────
def fetch_balance(engine: KisEngine) -> tuple[list, dict]:
    account = engine.kis.primary
    resp = engine.kis.request(
        "/uapi/domestic-stock/v1/trading/inquire-balance",
        method="GET",
        params={
            "CANO": account.number,
            "ACNT_PRDT_CD": account.code,
            "AFHR_FLPR_YN": "N",        # 시간외단일가 미반영
            "OFL_YN": "",               # 오프라인여부(공란)
            "INQR_DVSN": "02",          # 01:대출일별 02:종목별
            "UNPR_DVSN": "01",          # 단가구분
            "FUND_STTL_ICLD_YN": "N",   # 펀드결제분 미포함
            "FNCG_AMT_AUTO_RDPT_YN": "N",
            "PRCS_DVSN": "00",          # 00:전일매매포함 01:미포함
            "CTX_AREA_FK100": "",
            "CTX_AREA_NK100": "",
        },
        headers={"tr_id": "TTTC8434R", "custtype": "P"},
        appkey_location="header", auth=True,
    )
    j = resp.json()
    if j.get("rt_cd") != "0":
        print(f"[A] 잔고조회 실패 rt_cd={j.get('rt_cd')} msg={j.get('msg1')}")
        return [], {}

    out1 = j.get("output1") or []
    out2_list = j.get("output2") or []
    out2 = out2_list[0] if out2_list else {}
    return out1, out2


def print_balance(out1: list, out2: dict):
    _rule("(A) 잔고조회 inquire-balance / TTTC8434R — 종목 인자 없음")
    if not out2:
        print("  output2 없음")
        return

    for key, label, note in CASH_FIELDS:
        if key not in out2:
            continue
        tail = f"   {note}" if note else ""
        print(f"  {label:<18} {key:<20} {_won(out2[key])}{tail}")

    held = [r for r in out1 if _dec(r.get("hldg_qty")) > 0]
    print(f"\n  보유종목 {len(held)}건")
    for r in held:
        print(f"    {r.get('pdno')} {str(r.get('prdt_name') or '')[:14]:<16}"
              f" 수량 {_dec(r.get('hldg_qty')):>8,.0f}"
              f" 평가 {_won(r.get('evlu_amt'))}"
              f" 손익 {_won(r.get('evlu_pfls_amt'))}")


# ──────────────────────────────────────────────────────────────────
# (B) 매수가능조회 — inquire-psbl-order / TTTC8908R
#     broker.orderable() 과 같은 파라미터로 종목만 바꿔 반복 호출한다.
# ──────────────────────────────────────────────────────────────────
def fetch_psbl(engine: KisEngine, code: str, ord_dvsn: str = "01", unpr: int = 0) -> dict:
    account = engine.kis.primary
    resp = engine.kis.request(
        "/uapi/domestic-stock/v1/trading/inquire-psbl-order",
        method="GET",
        params={
            "CANO": account.number,
            "ACNT_PRDT_CD": account.code,
            "PDNO": code,
            "ORD_UNPR": str(unpr),
            "ORD_DVSN": ord_dvsn,          # 01=시장가(증거금율 반영) 00=지정가
            "CMA_EVLU_AMT_ICLD_YN": "N",
            "OVRS_ICLD_YN": "N",
        },
        headers={"tr_id": "TTTC8908R", "custtype": "P"},
        appkey_location="header", auth=True,
    )
    j = resp.json()
    if j.get("rt_cd") != "0":
        print(f"  [{code}] 매수가능조회 실패 rt_cd={j.get('rt_cd')} msg={j.get('msg1')}")
        return {}
    return j.get("output") or {}


def print_psbl_table(results: dict[str, dict]):
    """종목별 매수가능조회 결과를 필드 기준 가로 비교표로 출력."""
    _rule("(B) 매수가능조회 inquire-psbl-order / TTTC8908R — ORD_DVSN=01(시장가)")
    codes = [c for c in results if results[c]]
    if not codes:
        print("  조회 결과 없음")
        return

    head = "  " + f"{'필드':<20}" + "".join(f"{c:>18}" for c in codes)
    print(head)
    print("  " + "-" * (20 + 18 * len(codes)))
    for key, label, note in PSBL_FIELDS:
        row = "  " + f"{label:<20}"
        for c in codes:
            row += _won(results[c].get(key))
        tail = f"   {note}" if note else ""
        print(row + tail)


def diagnose(results: dict[str, dict], out2: dict):
    """삼성전자 기준값과 나머지 종목의 편차를 진단."""
    _rule("(C) 진단 — 삼성전자 프록시가 만드는 오차")

    ref = results.get(REF_CODE) or {}
    if not ref:
        print(f"  기준종목 {REF_CODE} 조회 실패 → 진단 생략")
        return

    ref_amt = _dec(ref.get("nrcvb_buy_amt"))
    print(f"  기준: {REF_CODE} nrcvb_buy_amt = {_won(ref_amt)}"
          f"   ← 지금 user_wallet.user_balance 에 들어가는 값\n")

    spreads = []
    for code, o in results.items():
        if not o or code == REF_CODE:
            continue
        amt = _dec(o.get("nrcvb_buy_amt"))
        diff = amt - ref_amt
        pct = (diff / ref_amt * 100) if ref_amt else Decimal(0)
        spreads.append(abs(pct))
        mark = "  " if abs(pct) < 1 else "⚠ "
        print(f"  {mark}{code}  nrcvb_buy_amt={_won(amt)}  "
              f"기준대비 {diff:>+16,.0f} ({pct:>+7.2f}%)")

    if spreads:
        mx = max(spreads)
        print()
        if mx < 1:
            print(f"  → 종목별 편차 최대 {mx:.2f}%. 사실상 계좌 단위 값으로 보인다.")
            print("    이 경우 오차는 금액이 아니라 '수량'(nrcvb_buy_qty)에서만 발생한다.")
        else:
            print(f"  ⚠ 종목별 편차 최대 {mx:.2f}%. 계좌 단위 값이 아니다.")
            print("    2026-09-30 대조 시점의 전제(종목 무관)가 깨졌다는 뜻이다.")
            print("    → broker.CASH_REF_SYMBOL 프록시 조회를 재검토해야 한다.")

    # 잔고조회 현금값과의 관계
    if out2:
        dnca = _dec(out2.get("dnca_tot_amt"))
        d2 = _dec(out2.get("prvs_rcdl_excc_amt"))
        print(f"\n  잔고조회 대조:")
        print(f"    dnca_tot_amt(예수금총금액)      {_won(dnca)}")
        print(f"    prvs_rcdl_excc_amt(D+2)         {_won(d2)}")
        print(f"    nrcvb_buy_amt({REF_CODE} 기준)    {_won(ref_amt)}")
        print(f"      D+2 - 매수가능 = {d2 - ref_amt:>+16,.0f}")
        print(f"      (양수면 미체결 주문에 묶인 금액 / 증거금 차감분일 가능성)")


# ──────────────────────────────────────────────────────────────────
# (D) DB user_wallet 현재 스냅샷
# ──────────────────────────────────────────────────────────────────
def print_db_wallet(user_id: int):
    _rule("(D) DB user_wallet 현재값")
    try:
        from sqlalchemy import text
        from stock_shared.db.contextManager import get_session

        sql = text("SELECT user_balance, stock_amount, total_asset, updated_at "
                   "FROM user_wallet WHERE user_id = :uid")
        with get_session() as s:
            row = s.execute(sql, {"uid": user_id}).mappings().first()
        if not row:
            print(f"  user_id={user_id} user_wallet 행 없음")
            return
        print(f"  user_balance  {_won(row['user_balance'])}   ← 매수가능금액(삼성전자 기준)이 저장됨")
        print(f"  stock_amount  {_won(row['stock_amount'])}")
        print(f"  total_asset   {_won(row['total_asset'])}")
        print(f"  updated_at    {row['updated_at']}")
    except Exception as e:  # noqa: BLE001
        print(f"  DB 조회 실패(무시 가능): {e}")


def main():
    ap = argparse.ArgumentParser(
        description="예수금/매수가능금액 대조 프로브 (조회 전용)")
    ap.add_argument("--user-id", type=int,
                    default=int(os.getenv("KIS_USER_ID") or 0) or None,
                    help="user_detail 에서 KIS 키를 꺼낼 user_id (기본: env KIS_USER_ID)")
    ap.add_argument("--codes", type=str, default="",
                    help="쉼표구분 종목코드. 미지정 시 삼성전자+보유종목+기본비교군")
    ap.add_argument("--no-db", action="store_true", help="DB user_wallet 조회 생략")
    args = ap.parse_args()

    if not args.user_id:
        ap.error("--user-id 를 지정하거나 KIS_USER_ID 환경변수를 설정하세요.")

    print(f"\n{'=' * 86}")
    print(f"  예수금 / 매수가능금액 대조 — user_id={args.user_id}")
    print(f"{'=' * 86}")

    engine = KisEngine(user_id=args.user_id)
    acct = engine.kis.primary
    print(f"  계좌: {acct.number}-{acct.code}  (id={engine.id})")

    # (A) 잔고조회
    out1, out2 = fetch_balance(engine)
    print_balance(out1, out2)

    # 조회 대상 종목 구성
    if args.codes:
        codes = [c.strip() for c in args.codes.split(",") if c.strip()]
    else:
        held = [r.get("pdno") for r in out1 if _dec(r.get("hldg_qty")) > 0]
        codes = list(dict.fromkeys([REF_CODE] + held + DEFAULT_EXTRA_CODES))

    # (B) 종목별 매수가능조회
    results = {c: fetch_psbl(engine, c) for c in codes}
    print_psbl_table(results)

    # (C) 진단
    diagnose(results, out2)

    # (D) DB
    if not args.no_db:
        print_db_wallet(args.user_id)

    _rule()
    print("  ※ 위 (A) 값들을 MTS/HTS 계좌 화면과 직접 대조해 보세요.")
    print("    '예수금'=dnca_tot_amt / 'D+2예수금'=prvs_rcdl_excc_amt 가 맞는지가 핵심입니다.\n")


if __name__ == "__main__":
    main()
