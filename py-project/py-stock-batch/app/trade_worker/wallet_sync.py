"""
user_wallet 잔고 동기화 헬퍼.

체결 직후/부팅 시 DB user_wallet 을 **실제 KIS 예수금**과 맞춘다.
실제 조회가 가능하고 sync=True 면 실제값을 정본(source of truth)으로 삼고,
그렇지 않으면 계산값(computed)으로 대체한다.

계좌 실보유(user_holdings) 중 worker 미추적 종목 흡수 (2026-08-21, §11.4 대체 구현):
  reconcile_wallet 에 sell_executor 를 넘기면, 실제 계좌 보유 종목 전체를
  trade_worker_position(HOLDING) 과 대조해 **아직 worker 가 모르는 종목**(HTS/MTS
  등 타채널 매수분 포함)을 trade_worker_position 에 새로 편입한다.
  ⚠ 편입되는 순간부터 그 종목은 활성 운용모드(M1 등)의 손절/익절/트레일링/
  타임스탑 자동매도 판정 대상이 된다 — 사용자가 자동매매에 맡길 생각이 없던
  종목까지 알고리즘이 팔 수 있다는 뜻이다. 매도 수기등록(trade_worker_manual_sell)을
  걸어두면 그 종목은 이 자동판정 대신 지정가만 보므로(BaseSellExecutor 선제 확인)
  안전하지만, 등록 없이 그냥 보유만 하고 있던 종목도 이 폴링(WALLET_POLL_SEC,
  기본 30초) 한 번으로 동일하게 편입되어 모드 rule 의 대상이 된다 — 계좌 보유
  전체를 worker 감시하에 두겠다는 명시적 선택(2026-08-21)에 따른 동작이다.

  단, 편입된 포지션은 exclusive_flag='Y' 로 등록되어 BuyExecutor.allow_buy() 의
  "1포지션 원칙" 카운트에서는 빠진다 — 계좌에 있던 종목이 편입됐다고 worker
  자신의 09:00 자동매수까지 멈추면 안 되기 때문이다(매도 감시는 exclusive_flag
  와 무관하게 그대로 적용됨). repository.open_position_if_absent 참고.

계좌에서 사라진 포지션 정리 (2026-10-01, _close_vanished_positions):
  위 편입이 "계좌 → DB" 한 방향만 맞추고 있었다. 반대 방향(사용자가 HTS/MTS 로
  수기 전량매도해서 계좌에서 사라진 종목을 DB 에서 SOLD 로 닫는 것)은 두 경로만
  담당했다 — ① sell_executor._do_sell 의 '실제 보유 0' 체크, ② 부팅 대조
  (main._reconcile_positions). 그런데 ①은 **매도 트리거(hit_line) 가 먼저 걸려야**
  도달하는 코드다. 라인(stop/target/trail)이 전부 NULL 인 포지션은 hit_line 이
  영원히 None 을 반환하므로(sell_executor1.hit_line 의 `if stop and ...`) ①에
  도달할 방법이 없고, ②는 재기동 전까지 돌지 않는다.
  결과: 좀비 HOLDING 이 남아 allow_buy() 의 1포지션 카운트를 먹고 신규매수가
  며칠씩 멈췄다(2026-09-29 user_id=3 032580, 2026-10-01 user_id=1 018000).
  → 이제 이 폴링이 직접 닫는다. 단 "잔고 조회가 일시적으로 불완전할 수 있다"는
  기존 우려(_sync_tracked_qty 주석)를 그대로 존중해서, 한 번 안 보인다고 닫지
  않고 **연속 cfg.position_vanish_miss 회**(기본 3회 ≈ 90초) 안 보일 때만 닫는다.
"""
import logging
from decimal import Decimal
from typing import Optional

log = logging.getLogger("trade_worker.wallet")


def _stock_snapshot(broker, repo, user_id):
    """실제 보유종목을 user_holdings 에 갱신하고 (평가금액 합계, holdings 목록) 반환.
    조회 실패 시 (None, None)."""
    holdings = broker.account_holdings()
    if holdings is None:
        return None, None
    try:
        repo.replace_holdings(user_id, holdings)   # 종목별 내역 갱신
    except Exception as e:  # noqa: BLE001
        log.warning("user_holdings 갱신 실패: %s", e)
    stock_amount = sum((h["eval_amount"] for h in holdings), Decimal(0))
    return stock_amount, holdings


def _absorb_untracked_holdings(repo, user_id, sell_executor, holdings):
    """user_holdings(계좌 실보유) 에는 있는데 trade_worker_position(HOLDING) 에는
    없는 종목을 worker 감시 대상으로 편입한다.

    ⚠ 편입 직후부터 그 종목은 활성 운용모드의 자동 손절/익절/트레일링/타임스탑
    판정 대상이 된다(모듈 docstring 참고). sell_executor 가 없으면(호출부가 안
    넘겼으면) 아무것도 하지 않는다 — 초기 라인을 세울 strategy 가 없는 채로
    HOLDING 만 만들면 다음 daily 평가 전까지 무방비로 방치되기 때문이다.
    """
    if not holdings or sell_executor is None or sell_executor.strategy is None:
        return
    try:
        tracked = {p["stock_code"] for p in repo.get_holding_positions(user_id)}
    except Exception as e:  # noqa: BLE001
        log.warning("[편입] worker 포지션 조회 실패 → 편입 skip: %s", e)
        return

    absorbed = []
    for h in holdings:
        code = h.get("symbol")
        qty = h.get("qty")
        if not code or code in tracked or not qty or Decimal(str(qty)) <= 0:
            continue
        entry_price = Decimal(str(h.get("avg_price") or h.get("cur_price") or 0))
        if entry_price <= 0:
            continue
        try:
            inserted = repo.open_position_if_absent(user_id, code, h.get("name") or "",
                                                     entry_price, Decimal(str(qty)))
        except Exception as e:  # noqa: BLE001
            log.warning("[편입] %s open_position 실패: %s", code, e)
            continue
        if not inserted:
            continue   # 그 사이 다른 경로로 이미 편입됨(레이스) — 정상 진행
        log.info("[편입] %s(%s) %s주 @%s → worker 감시 대상 편입(외부보유 흡수, 모드 자동매도 대상됨)",
                 h.get("name"), code, qty, entry_price)
        try:
            lines = sell_executor.strategy.initial_lines(code, float(entry_price))
            repo.update_position_state(user_id, code, lines)
            log.info("[편입] %s 초기라인 stop=%s target=%s atr=%s",
                     code, lines.get("stop_price"), lines.get("target_price"),
                     lines.get("entry_atr"))
        except Exception as e:  # noqa: BLE001
            log.warning("[편입] %s 초기 라인 계산 실패(라인 없이 HOLDING 상태로 남음): %s", code, e)
        absorbed.append(code)

    if absorbed:
        # 방금 편입한 종목을 즉시 실시간 감시(소켓 구독)에 태운다.
        # 안 하면 다음 reload_positions(개장 루틴/재기동)까지 실시간 감시 사각지대가 생긴다.
        try:
            sell_executor.reload_positions(reset_sold=False)
        except Exception as e:  # noqa: BLE001
            log.warning("[편입] reload_positions 실패: %s", e)


def _sync_tracked_qty(repo, user_id, sell_executor, holdings):
    """이미 편입된(trade_worker_position HOLDING) 종목의 수량을 계좌 실보유로 보정한다.

    _absorb_untracked_holdings 는 **새 종목 편입만** 하므로, 편입 이후 타채널(HTS/MTS)
    추가매수·부분매도가 있으면 DB 포지션 수량이 실보유와 어긋난 채로 남았다
    (부팅 대조 _reconcile_positions 에서만 보정됐음). 그 결과 매도 수기등록 수량이
    min(DB수량, 실보유) 로 잘려 덜 팔리고 티어가 DONE 처리되는 사고가 났다
    (2026-08-27 091590: 184주 등록 → 11주만 매도).

    - 보정 대상: 계좌에 있고 DB 에도 HOLDING 인 종목 중 수량이 다른 것.
    - 계좌에 없는 종목(청산 추정)은 여기서 닫지 않는다 — 잔고 조회가 일시적으로
      불완전할 수 있어 오판 청산 위험이 있다. 매도 시점 _do_sell 의 실보유 0 체크와
      부팅 대조가 처리한다.
    - 매도 주문 진행중(_inflight) 종목은 건너뛴다 — 체결 반영(reduce_position)과
      경합해 수량을 되돌려 쓰는 것을 피한다. 혹시 경합이 나도 다음 폴링에서 다시 맞춰진다.
    """
    if not holdings or sell_executor is None:
        return
    try:
        rows = repo.get_holding_positions(user_id)
    except Exception as e:  # noqa: BLE001
        log.warning("[수량보정] worker 포지션 조회 실패 → skip: %s", e)
        return
    held = {h.get("symbol"): Decimal(str(h.get("qty") or 0)) for h in holdings if h.get("symbol")}
    inflight = set(getattr(sell_executor, "_inflight", ()) or ())
    for p in rows:
        code = p.get("stock_code")
        if code not in held or code in inflight:
            continue
        real = held[code]
        db_qty = Decimal(str(p.get("hold_qty") or 0))
        if real <= 0 or real == db_qty:
            continue
        try:
            repo.update_position_qty(user_id, code, real)
        except Exception as e:  # noqa: BLE001
            log.warning("[수량보정] %s DB 갱신 실패: %s", code, e)
            continue
        lock = getattr(sell_executor, "_lock", None)
        positions = getattr(sell_executor, "positions", None)
        if positions is not None:
            if lock is not None:
                with lock:
                    if code in positions:
                        positions[code]["hold_qty"] = real
            elif code in positions:
                positions[code]["hold_qty"] = real
        msg = "[수량보정] %s 포지션 %s → %s주 (계좌 실보유 기준)"
        log.info(msg, code, db_qty, real)
        wlog = getattr(sell_executor, "wlog", None)
        if wlog is not None:
            try:
                wlog.info(msg, code, db_qty, real)
            except Exception:  # noqa: BLE001
                pass


def _vanished_exit_price(broker, code):
    """외부청산 추정 청산가. 실패하면 None → pnl 을 NULL 로 남긴다.

    실제 체결가는 알 수 없다(사용자가 타채널에서 이미 팔았다). 0 을 넣으면
    "0원에 팔아 전액 손실" 로 기록되므로, 모르면 NULL 로 두는 편이 정확하다.
    """
    if broker is None:
        return None
    try:
        px = broker.current_price(code)
        return px if px and px > 0 else None
    except Exception as e:  # noqa: BLE001
        log.warning("[외부청산] %s 추정가 조회 실패 → pnl 미기록: %s", code, e)
        return None


def _close_vanished_positions(repo, user_id, sell_executor, holdings, broker=None):
    """trade_worker_position(HOLDING) 인데 계좌 실보유에 없는 종목을 외부청산으로 닫는다.

    왜 폴링이 직접 닫아야 하는지는 모듈 docstring 참고(기존 두 경로가 라인 유무와
    재기동에 종속돼 있어 좀비 포지션이 남았다).

    오판 청산 방지 가드:
      - holdings 가 None(조회 실패)이면 호출되지 않는다(_stock_snapshot 반환값).
      - 종목별 연속 미발견 횟수가 cfg.position_vanish_miss 에 도달해야 닫는다.
        한 번이라도 계좌에서 보이면 카운터를 리셋한다.
      - 매도 주문 진행중(_inflight)은 건너뛴다 — 체결 반영(reduce_position)과
        경합해 방금 체결된 포지션을 EXTERNAL_CLOSED 로 덮어쓰는 것을 피한다.
      - 카운터는 sell_executor 인스턴스에 들고 있다(프로세스 생명주기). 재기동하면
        0 부터 다시 세는데, 재기동 시점엔 부팅 대조가 같은 일을 하므로 문제없다.
    """
    if holdings is None or sell_executor is None:
        return
    try:
        rows = repo.get_holding_positions(user_id)
    except Exception as e:  # noqa: BLE001
        log.warning("[외부청산] worker 포지션 조회 실패 → skip: %s", e)
        return
    if not rows:
        return

    held = {h.get("symbol") for h in holdings if h.get("symbol")}
    inflight = set(getattr(sell_executor, "_inflight", ()) or ())
    misses = getattr(sell_executor, "_acct_miss", None)
    if misses is None:
        misses = {}
        sell_executor._acct_miss = misses
    threshold = max(1, int(getattr(getattr(sell_executor, "cfg", None), "position_vanish_miss", 3)))
    wlog = getattr(sell_executor, "wlog", None)

    tracked = set()
    for p in rows:
        code = p.get("stock_code")
        if not code:
            continue
        tracked.add(code)
        if code in inflight:
            continue
        if code in held:
            misses.pop(code, None)
            continue

        n = misses.get(code, 0) + 1
        misses[code] = n
        if n < threshold:
            log.info("[외부청산] %s 계좌 미보유 %d/%d회 → 관망(오판 방지)", code, n, threshold)
            continue

        try:
            # 수량 None → 포지션 보유수량(전량)을 쓴다. 가격은 추정치(없으면 NULL).
            repo.close_position(user_id, code, _vanished_exit_price(broker, code), None,
                                "EXTERNAL_CLOSED")
        except Exception as e:  # noqa: BLE001
            log.warning("[외부청산] %s 포지션 종료 실패: %s", code, e)
            continue
        misses.pop(code, None)

        # DB 를 닫았으면 메모리/구독도 같이 정리해야 한다 — 안 하면 다음 틱마다
        # 이미 없는 포지션을 계속 평가하고, 라인에 닿으면 실주문까지 나간다.
        try:
            sell_executor.discard_position(code)
        except Exception as e:  # noqa: BLE001
            log.warning("[외부청산] %s 감시 해제 실패: %s", code, e)

        msg = "[외부청산] %s 계좌 실보유 없음 %d회 연속 → 포지션 종료(SOLD) · 타채널 수기매도 추정"
        log.warning(msg, code, threshold)
        if wlog is not None:
            try:
                wlog.warn(msg, code, threshold)
            except Exception:  # noqa: BLE001
                pass
        notifier = getattr(sell_executor, "notifier", None)
        if notifier is not None:
            try:
                # alert(= send + push). 포지션이 worker 모르게 사라진 건 보유현황이
                # 바뀌는 일이라 앱에서도 바로 알아야 하므로 텔레그램/이메일만으로
                # 끝내지 않는다. push 본문은 배너 한 줄로 잘리므로 따로 넘긴다.
                notifier.alert(
                    "[외부청산] 포지션 자동 종료",
                    f"{code} 가 계좌 실보유에서 {threshold}회 연속 사라져 "
                    f"trade_worker_position 을 SOLD 로 닫았습니다"
                    f"(타채널 수기매도 추정). 신규매수 차단이 해제됩니다.",
                    push_body=f"{code} 포지션을 자동 종료했습니다 · 타채널 수기매도 추정",
                    data={"event": "POSITION_CLOSED", "reason": "EXTERNAL",
                          "stock_code": code},
                )
            except Exception:  # noqa: BLE001
                pass

    # 더 이상 HOLDING 이 아닌 종목의 카운터는 흘려보낸다(메모리 누수 방지).
    for code in [c for c in misses if c not in tracked]:
        misses.pop(code, None)


def reconcile_wallet(broker, repo, user_id: int,
                     computed: Optional[Decimal] = None,
                     sync: bool = True, tag: str = "",
                     sell_executor=None) -> Decimal:
    """실제 계좌 기준으로 user_wallet 스냅샷을 갱신하고 **매수가능금액**을 반환.

    ⚠ 반환값과 user_balance 는 예수금이 아니라 매수가능금액(nrcvb_buy_amt)이다.
      예수금(ord_psbl_cash)은 deposit 컬럼에 따로 적재한다 — 표시 전용.
      증거금징수율·미체결 주문 때문에 두 값은 서로 다르다(broker.AccountCash 참고).

    매수가능금액:
      1) 실제 조회 성공 & sync=True → 실제값(정본)
      2) 아니면 computed 값(수수료/세금 미반영 근사)
      3) 둘 다 없으면 DB 현재값
    보유주식평가/총자산: 실제 보유종목 조회로 함께 갱신(조회 실패 시 현금만).

    sell_executor 를 넘기면 포지션 3종 대조를 함께 수행한다:
      1) _sync_tracked_qty          : 이미 편입된 종목의 수량을 실보유로 보정
      2) _close_vanished_positions  : 계좌에서 사라진 HOLDING 을 외부청산 종료
                                      (연속 cfg.position_vanish_miss 회 미발견 시)
      3) _absorb_untracked_holdings : 계좌 실보유 중 worker 미추적 종목 편입
                                      (⚠ 모드 자동매도 대상이 됨)
    2)를 3) 앞에 두는 이유: 같은 폴링에서 닫은 종목을 다시 편입하지 않도록 —
    애초에 계좌에 없어서 닫은 것이므로 3) 의 편입 대상에도 들어오지 않는다.
    """
    actual = broker.account_cash()          # AccountCash | None
    deposit = actual.deposit if actual is not None else None
    if actual is not None and sync:
        cash = Decimal(actual.buyable)
    elif computed is not None:
        cash = Decimal(computed)
    else:
        return repo.get_wallet_balance(user_id)

    stock_amount, holdings = _stock_snapshot(broker, repo, user_id)
    # 총자산은 '예수금 + 주식평가' 다. 매수가능금액(cash)으로 잡으면 화면에서
    # 예수금 + 주식평가 ≠ 총자산 이 되어 어긋난다. 예수금 조회 실패 시에만 cash 로 대체.
    asset_cash = deposit if deposit is not None else cash
    total = (asset_cash + stock_amount) if stock_amount is not None else None
    repo.set_wallet_snapshot(user_id, cash=cash, stock_amount=stock_amount, total_asset=total,
                             deposit=deposit)
    log.info("[%s] user_wallet ← 매수가능 %s · 예수금 %s · 보유평가 %s · 총자산 %s (실제조회=%s,sync=%s)",
             tag, cash, deposit, stock_amount, total, actual is not None, sync)

    _sync_tracked_qty(repo, user_id, sell_executor, holdings)        # 기존 편입 종목 수량 보정
    _close_vanished_positions(repo, user_id, sell_executor, holdings, broker)  # 계좌에서 사라진 포지션 종료
    _absorb_untracked_holdings(repo, user_id, sell_executor, holdings)

    return cash
