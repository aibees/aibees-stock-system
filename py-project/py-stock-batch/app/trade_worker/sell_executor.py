"""
매도 엔진 — 실시간 소켓 감시.

판정 분리 (docs_buy_target_sim_spec.md §4 기준):
  - 실시간(소켓): 체결가가 stop_price / target_price / trail_line 을 돌파하면 즉시 매도.
  - 개장 시(refresh_positions): 일봉 신호(OBV 데드크로스·타임스탑 등으로 action_type 이
    SELL 계열로 마킹된) 포지션을 정리. (일봉 지표는 실시간 판정 불가)

트레일링 고점(peak_high) 생명주기:
  1) 매수 체결   : repository.open_position 이 peak_high = 진입가로 초기화
  2) 장중        : on_price → _advance_peak 이 **메모리에서만** 갱신하고 trail_line 재계산.
                   틱마다 DB 를 때리지 않는다(_peak_dirty 로 변경분만 표시).
  3) 세션 종료   : flush_peaks() 가 메모리 peak_high / trail_line 을 DB 에 1회 저장.
                   KRX 전용은 15:30, NXT 대상은 20:00 이후(main.py cron).
  4) 다음날 부팅 : reload_positions 가 DB 에서 다시 읽어 메모리로 이어받는다.
  고점 기준은 peak_high 단일이다. 구 trail_basis('close'/'high') 선택 개념은 제거됐다.

거래 세션 분리 (broker.market_session):
  - NXT 대상(master_stock.nxt_flag='Y'): 08:00~08:50 프리마켓(지정가) · 09:00~15:20 메인(시장가)
    · 15:20~15:30 KRX 단독(시장가) · 15:30~20:00 애프터마켓(지정가)
  - KRX 전용: 09:00~15:30 만 (시장가)
  통합 실시간 스트림(H0UNCNT0)은 장외에도 틱이 오므로, 세션 가드 없이는 KRX 가 닫힌
  시간에 SOR 시장가가 나가 거부되고 연속 실패로 종목이 자동 비활성된다.

체결 → sold 처리 · 잔고 증가 · trade_log.

매도 수기등록(지정가, 모드 무관, sql/08_manual_sell_order_ddl.sql +
09_manual_sell_multi_ddl.sql):
  trade_worker_manual_sell 에 ARMED 행이 있는 종목은 위 두 판정 경로(on_price 의
  hit_line, refresh_positions 의 strategy.evaluate) 를 **둘 다** 건너뛰고
  sell_price 도달 여부만 본다 — 활성 운용모드가 M1/M2/M3 무엇이든 동일하다
  (reload_manual_sells 참고). 사용자가 "이 종목은 자동 rule 대신 이 가격에
  팔아달라"고 등록해두면 모드 전략보다 우선한다는 뜻. 등록 자체는 계좌 실보유
  (user_holdings)만 있으면 worker 자기매수 여부와 무관하게 할 수 있다
  (router_auto_trade.py 참고) — 다만 실시간 판정 대상은 self.positions
  (trade_worker_position HOLDING)에 있는 종목뿐이다. worker 가 직접 산 게
  아니어도(HTS/MTS 등 타채널 매수) wallet_sync.reconcile_wallet 이 주기적으로
  (WALLET_POLL_SEC, 기본 30초) 계좌 실보유를 대조해 자동 편입하므로(2026-08-21,
  §11.4 대체 구현) 등록 후 한 폴링 주기 안에는 감시가 시작된다. 다만 그 편입은
  이 종목 하나만 지정가로 지키는 게 아니라 **활성 운용모드의 자동 손절/익절/
  트레일링/타임스탑 대상으로도** 편입한다는 뜻이라, 수기등록 없이 그냥 보유만
  하던 종목도 같이 편입되면 알고리즘이 임의로 팔 수 있다(wallet_sync.py 참고).

  다건화(2026-08-21): 종목 하나에 지정가를 여러 개(사다리 매도 — 예 30%@50000·
  30%@55000·40%@60000) 등록할 수 있고, 여러 종목에 동시 등록할 수도 있다.
  _manual_sells 는 symbol → 티어 리스트(sell_price 오름차순)로 관리한다.
  on_price 는 그 틱에서 가격이 도달한 티어 중 **가장 낮은 가격의 미체결 티어
  1건**만 매도한다(가격이 여러 티어를 한 번에 건너뛰어도 다음 틱에서 마저
  처리된다 — 틱당 1건으로 제한해 무한루프를 피한다). 각 티어의 매도수량은
  등록 시점 보유수량 스냅샷(base_qty)에 그 티어의 qty_ratio 를 곱한 절대수량으로
  고정된다(repository.insert_manual_sell 참고) — 그래야 먼저 체결된 티어 때문에
  다음 티어의 비율 기준(실보유)이 줄어들어 의도한 수량보다 적게 팔리는 일이 없다.
"""
import threading
import time
from abc import ABC, abstractmethod
from decimal import ROUND_DOWN, Decimal

from app.trade_worker.broker import Broker
from app.trade_worker.config import WorkerConfig
from app.trade_worker.repository import Repository
from app.trade_worker.wallet_sync import reconcile_wallet
from app.trade_worker.worklog import WorkerLogger

# Decimal 로 변경
def _toDecimal(v):
    return Decimal(str(v)) if v is not None else None


class BaseSellExecutor(ABC):
    def __init__(self, cfg: WorkerConfig, broker: Broker, repo: Repository, notifier=None, strategy=None):
        self.cfg = cfg
        self.broker = broker
        self.repo = repo
        self.notifier = notifier
        self.strategy = strategy          # SellStrategy (일별 라인/액션 계산)
        # 모든 로그는 trade_worker_log DB 테이블에 시간순 적재
        self.wlog = WorkerLogger(repo, cfg.user_id, "sell")
        self.positions: dict[str, dict] = {}   # symbol -> position row
        self._tickets: dict[str, object] = {}  # symbol -> 구독 티켓(종목별 해제용)
        self._subscribed: set[str] = set()     # 이미 시세 구독한 종목(중복 구독 방지)
        self._sold: set[str] = set()           # 당일 매도 완료(개장 reload 시 초기화)
        self._inflight: set[str] = set()       # 매도 주문 진행중(동시 중복주문 방지)
        self._cooldown: dict[str, float] = {}  # 실패 후 재시도 금지 만료시각(폭주 방지)
        self._fail_count: dict[str, int] = {}  # 종목별 연속 실패 횟수
        self._disabled: set[str] = set()       # 연속 실패로 자동 비활성(수동 확인 필요)
        self._untradable_log: dict[str, float] = {}  # 장외 라인돌파 로그 throttle 만료시각
        self._peak_dirty: set[str] = set()     # 장중 고점이 갱신돼 flush 대상인 종목
        self._peak_log: dict[str, float] = {}  # 고점 갱신 로그 throttle 만료시각
        self._pending_reason: dict[str, str] = {}  # order_no -> 잔여 주문의 매도 사유
        self._pending_manual_id: dict[str, int] = {}  # order_no -> 잔여 주문의 수기등록 티어 id
        # ⚠ symbol 이 아니라 order_no 로 키를 잡는다 — 사다리 매도(종목당 여러 티어)에서는
        # 한 종목에 티어 A 의 주문이 아직 지연체결 추적 중인 상태로 쿨다운이 풀려 티어 B 의
        # 주문이 나갈 수 있다. symbol 키였다면 나중 주문이 먼저 것의 pending 정보를
        # 덮어써 late-fill 이 엉뚱한 티어를 완료 처리하는 사고가 난다.
        self._manual_sells: dict[str, list[dict]] = {}  # symbol -> 매도 수기등록(ARMED) 티어 리스트(가격 오름차순). 있으면 모드 rule 무시
        self._lock = threading.Lock()

    # ── 구독 시작 ────────────────────────────────────────────────────
    def start(self):
        # 체결통보 구독은 broker.start_fill_tracking() 이 담당(main). 여기선 시세만.
        self.reload_positions()
        self.reload_manual_sells()

    # ── 매도 수기등록(지정가, 모드 무관) 재적재 ─────────────────────────
    def reload_manual_sells(self):
        """trade_worker_manual_sell(ARMED) 재적재.

        등록된 종목은 **현재 활성 운용모드가 무엇이든**(M1/M2/M3) 그 모드의
        자동 매도 rule(hit_line/일봉 신호)을 보지 않고 여기 담긴 sell_price
        도달 여부만으로 매도한다 — on_price/refresh_positions 에서 모드 판정보다
        먼저(선제) 확인한다. apply_settings_change() 폴링 주기(기본 60초)에
        같이 불려 화면에서 등록/취소한 내역을 반영한다.

        종목당 여러 티어(사다리 매도)를 지원하므로 symbol → 리스트로 묶고,
        가격 오름차순으로 정렬해둔다 — on_price 가 "가장 낮은 미도달 티어"부터
        순서대로 확인할 수 있게 하기 위함이다.
        """
        try:
            rows = self.repo.get_active_manual_sells(self.cfg.user_id)
        except Exception as e:  # noqa: BLE001  (테이블 미생성 등 — worker 는 죽지 않는다)
            self.wlog.warn("[매도] 수기등록 조회 실패: %s", e)
            return
        fresh: dict[str, list[dict]] = {}
        for r in rows:
            fresh.setdefault(r["stock_code"], []).append(r)
        for tiers in fresh.values():
            tiers.sort(key=lambda t: Decimal(str(t["sell_price"])))
        with self._lock:
            added = fresh.keys() - self._manual_sells.keys()
            removed = self._manual_sells.keys() - fresh.keys()
            self._manual_sells = fresh
        for code in added:
            if code not in self.positions:
                # 아직 trade_worker_position 에 없는 종목 — wallet_sync.reconcile_wallet
                # 의 주기 편입(WALLET_POLL_SEC)이 이 종목을 계좌 실보유에서 찾아 넣어줄
                # 때까지 일시적으로 감시 밖이다(영구 미구현이 아니라 다음 폴링까지의 지연).
                self.wlog.warn("[매도] %s 수기등록됐지만 아직 worker 편입 전 → 다음 계좌 동기화 후 감시 시작",
                               code)
                continue
            prices = ", ".join(str(t.get("sell_price")) for t in fresh[code])
            self.wlog.info("[매도] %s 수기등록 감지 @[%s] → 이후 자동 rule 대신 지정가만 감시",
                           code, prices)
        for code in removed:
            self.wlog.info("[매도] %s 수기등록 해제(취소/체결) → 자동 rule 로 복귀", code)

    def _complete_manual_if_needed(self, symbol: str, reason: str, fill_px, filled_qty,
                                   manual_id: int | None = None):
        """MANUAL_SELL 로 체결됐으면 해당 티어(manual_id)만 trade_worker_manual_sell 을
        DONE 으로 닫는다. 같은 종목에 등록된 다른 티어(사다리 매도)는 건드리지 않는다 —
        그래서 전량 소진(remain=0) 여부와 무관하게 "이번에 체결된 티어"만 완료 처리한다."""
        if reason != "MANUAL_SELL" or manual_id is None:
            return
        try:
            self.repo.complete_manual_sell(self.cfg.user_id, manual_id, fill_px, filled_qty)
        except Exception as e:  # noqa: BLE001
            self.wlog.warn("[매도] %s(id=%s) 수기등록 완료 처리 실패: %s", symbol, manual_id, e)
        with self._lock:
            tiers = self._manual_sells.get(symbol)
            if tiers is not None:
                tiers[:] = [t for t in tiers if t.get("id") != manual_id]
                if not tiers:
                    self._manual_sells.pop(symbol, None)

    """
    worker 보유(trade_worker_position HOLDING) 종목을 감시 대상으로 갱신.
    - 감시 대상 = worker 가 직접 매수한 HOLDING 만 (trade_sell_target_stock 과 무관)
    - _sold 초기화(당일 리셋), 미구독 종목만 신규 시세 구독
    """
    def reload_positions(self, reset_sold: bool = True):
        """reset_sold=False 는 **매수 직후 재적재 전용**.
        당일 이미 판 종목의 _sold 마킹을 지우지 않기 위해서다."""
        # trade_worker_position 에서 HOLDING 상태의 종목들
        holding = self.repo.get_holding_positions(self.cfg.user_id)

        fresh = {p["stock_code"]: p for p in holding}
        # DB 재적재로 장중 메모리 고점이 날아가지 않도록 이어붙인다.
        # (프리마켓 매수 직후 등 세션 도중에도 reload 가 불린다)
        with self._lock:
            for code, new_pos in fresh.items():
                old = self.positions.get(code)
                if not old:
                    continue
                for key in ("peak_high", "trail_line", "last_atr"):
                    old_v, new_v = old.get(key), new_pos.get(key)
                    if old_v is None:
                        continue
                    # peak_high 는 더 높은 쪽을 유지, 나머지는 메모리 값 우선
                    if key == "peak_high" and new_v is not None:
                        new_pos[key] = max(float(old_v), float(new_v))
                    else:
                        new_pos[key] = old_v
            self.positions = fresh
            # 더 이상 보유하지 않는 종목의 dirty 마킹 정리
            self._peak_dirty &= set(fresh)
        if reset_sold:
            self._sold = set()
        # self.wlog.info("[매도] HOLDING(감시대상) %d종목 · 실시간시세 구독중 %d종목",
        #                len(holding), len(self._subscribed))
        for code, pos in self.positions.items():
            if code in self._subscribed:
                continue
            try:
                nxt = (pos.get("nxt_flag") == "Y")   # NXT 대상 → 통합 스트림(H0UNCNT0)
                self._tickets[code] = self.broker.subscribe_price(code, self.on_price, nxt=nxt)
                self._subscribed.add(code)
            except Exception as e:  # noqa: BLE001
                self.wlog.warn("[매도] %s price 구독 실패: %s", code, e)

    def _unsubscribe(self, symbol: str):
        """보유 종료(매도 완료/외부청산) 종목의 실시간 시세 구독 해제.
        보유중(active)일 때만 소켓 감시하고, 팔고 나면 즉시 구독을 끊어 리소스를 정리한다."""
        ticket = self._tickets.pop(symbol, None)
        self._subscribed.discard(symbol)
        if ticket is not None:
            try:
                ticket.unsubscribe()
            except Exception as e:  # noqa: BLE001
                self.wlog.warn("[매도] %s 구독 해제 실패: %s", symbol, e)

    # ── 세션 가드 ────────────────────────────────────────────────────
    def _session(self, pos: dict):
        """이 종목이 지금 주문 가능한 세션인지. NXT 대상과 KRX 전용은 창이 다르다.
          - NXT 대상 : 08:00~08:50(지정가) · 09:00~15:20 · 15:20~15:30 · 15:30~20:00(지정가)
          - KRX 전용 : 09:00~15:30 만
        통합 스트림(H0UNCNT0)은 장외에도 틱을 뿜기 때문에 이 가드가 없으면
        KRX 닫힌 시간에 SOR 시장가가 나가 '장운영시간이 아닙니다'로 거부되고,
        _register_fail 이 쌓여 종목이 자동 비활성(_disabled)까지 간다."""
        return self.broker.market_session(pos.get("nxt_flag") == "Y")

    # ── 실시간 라인 돌파 ─────────────────────────────────────────────
    def on_price(self, symbol: str, price: Decimal):
        pos = self.positions.get(symbol)
        if not pos or symbol in self._sold or symbol in self._inflight or symbol in self._disabled:
            return

        # 고점 갱신 + 트레일 라인 재계산을 먼저 한다.
        # 쿨다운 중이라도 고점 추적은 계속해야 라인이 뒤처지지 않는다.
        self._advance_peak(symbol, pos, price)

        # 실패 쿨다운 중이면 재시도 금지(폭주 방지)
        cd = self._cooldown.get(symbol)
        if cd and time.time() < cd:
            return

        # ── 매도 수기등록 우선(선제) 확인 ──────────────────────────────
        # 이 종목에 사용자가 지정가를 등록해뒀으면(종목당 여러 티어 가능),
        # 활성 운용모드가 무엇이든 그 모드의 hit_line(stop/target/trail)은
        # 아예 보지 않는다. 티어가 하나라도 있으면 그중 **가장 낮은 가격의
        # 미도달 티어**가 이 틱의 대상이다 — 도달했으면 그 티어 1건만 판다
        # (틱당 1건. 가격이 여러 티어를 한 번에 건너뛰어도 다음 틱에서 마저 처리).
        tiers = self._manual_sells.get(symbol)
        if tiers:
            tier = tiers[0]   # 가격 오름차순 정렬 → 첫 원소가 가장 낮은(=가장 먼저 도달할) 티어
            if Decimal(str(price)) < Decimal(str(tier["sell_price"])):
                return   # 아직 지정가 미도달 — 모드 rule 로 넘어가지 않고 계속 대기
            manual = tier
            reason = "MANUAL_SELL"
        else:
            manual = None
            reason = self.hit_line(pos, price)
            if not reason:
                return

        sess = self._session(pos)
        if not sess.tradable:
            # 주문 불가 시간대(예: NXT 08:50~09:00 휴식, 20:00 이후). 실패로 세지 않는다.
            self._warn_untradable(symbol, reason, sess)
            return
        if manual is not None:
            self.wlog.info("[매도] 수기등록 지정가 도달 %s @%s (목표=%s · %s)",
                           symbol, price, manual["sell_price"], sess.name)
        else:
            self.wlog.info("[매도] 라인 돌파 %s @%s (%s · %s)", symbol, price, reason, sess.name)
        self._do_sell(symbol, pos, price, reason, sess, manual=manual)

    def _warn_untradable(self, symbol: str, reason: str, sess):
        """장외 라인돌파 로그 — 소켓 틱마다 찍히면 폭주하므로 종목당 60초 1회로 제한."""
        now = time.time()
        if now < self._untradable_log.get(symbol, 0):
            return
        self._untradable_log[symbol] = now + 60
        self.wlog.info("[매도] %s 라인 돌파(%s) 감지했으나 %s → 주문 보류",
                       symbol, reason, sess.name)

    # ── 장중 설정 변경 반영 ──────────────────────────────────────────
    def apply_settings_change(self) -> bool:
        """user_options 가 바뀌었으면 전략을 갈아끼우고 라인을 즉시 재계산한다.

        worker 는 장시간 살아있는 데몬이라 부팅 때 configure() 한 값이 그대로 굳는다.
        이 메서드가 없으면 화면에서 손절/익절/트레일링을 바꿔도 **다음 재기동까지**
        반영되지 않는다.

        재계산 범위는 실시간 감시가 쓰는 stop/target/trail 3개 라인뿐이다.
        일봉 신호(OBV 데드크로스·타임스탑)는 다음 개장 루틴(refresh_positions)이
        맡는다 — 장중엔 당일 봉이 미완성이라 판정 자체가 성립하지 않는다.

        ⚠ 손절선을 조이면(예 5%→3%) 이미 그 아래인 종목은 **다음 틱에 즉시 매도**된다.
          의도된 동작이지만 사고 여지가 있어 변경 내역과 라인을 모두 로그로 남기고
          알림도 보낸다.
        """
        # 매도 수기등록은 전략(모드)과 무관하므로 strategy 유무와 상관없이 매번 재적재한다.
        self.reload_manual_sells()

        if not self.strategy:
            return False
        try:
            changes = self.strategy.reload_if_changed()
        except Exception as e:  # noqa: BLE001
            self.wlog.warn("[설정] user_options 조회 실패: %s", e)
            return False
        if not changes:
            return False

        summary = ", ".join(f"{a}: {o}→{n}" for a, o, n in changes[:8])
        if len(changes) > 8:
            summary += f" 외 {len(changes) - 8}건"

        # 운용모드 전환은 파라미터 조정과 급이 다르다 — 매매 방식 자체가 바뀐다.
        # 보유 종목이 없어 라인 재계산 대상이 0건이어도 반드시 알린다.
        mode_change = next((c for c in changes if c[0].startswith("active_mode")), None)
        if mode_change:
            key, old_mode, new_mode = mode_change
            failed = key.endswith("(전환실패)")
            if failed:
                self.wlog.warn("[설정] 운용모드 %s → %s 전환 실패(미구현) · 기존 전략 유지",
                               old_mode, new_mode)
                self._notify_mode_change(old_mode, new_mode, failed=True)
                # 전략이 그대로라 라인을 다시 계산할 이유가 없다.
                return False
            self.wlog.info("[설정] 운용모드 전환 %s → %s · 전략=%s",
                           old_mode, new_mode, type(self.strategy.strategy).__name__)
            self._notify_mode_change(old_mode, new_mode, failed=False)

        self.wlog.info("[설정] 변경 감지 → 전략 재적용 (%s)", summary)

        with self._lock:
            targets = list(self.positions.items())

        applied = 0
        for code, pos in targets:
            state = self.strategy.recalc_lines(pos)
            if not state:
                continue
            try:
                self.repo.update_position_state(self.cfg.user_id, code, state)
            except Exception as e:  # noqa: BLE001
                self.wlog.warn("[설정] %s 라인 저장 실패: %s", code, e)
                continue
            with self._lock:
                cur = self.positions.get(code)
                if cur is not None:
                    cur.update(state)
            applied += 1
            self.wlog.info("[설정] %s 라인 재계산 stop=%s target=%s trail=%s",
                           code, state.get("stop_price"), state.get("target_price"),
                           state.get("trail_line"))

        if self.notifier and applied:
            try:
                self.notifier.send("[설정 변경] 매도 전략 재적용",
                                   f"{applied}종목 라인 갱신\n{summary}")
            except Exception:  # noqa: BLE001
                pass
        return True

    def _notify_mode_change(self, old_mode, new_mode, failed: bool):
        """운용모드 전환 알림. 보유 종목이 0건이어도 반드시 보낸다 —
        매매 방식 자체가 바뀌는 사건이라 사용자가 몰라서는 안 된다."""
        if not self.notifier:
            return
        try:
            if failed:
                self.notifier.send(
                    f"[운용모드 전환 실패] {old_mode} → {new_mode}",
                    f"⚠️ 운용모드 <b>{new_mode}</b> 전략이 아직 구현되지 않아 전환하지 못했습니다.\n"
                    f"기존 <b>{old_mode}</b> 전략으로 계속 운용합니다.")
            else:
                self.notifier.send(
                    f"[운용모드 전환] {old_mode} → {new_mode}",
                    f"운용모드가 <b>{old_mode}</b> → <b>{new_mode}</b> 로 전환됐습니다.\n"
                    f"이후 매수/매도 판정은 새 모드 기준으로 동작합니다.")
        except Exception:  # noqa: BLE001
            pass

    # ── 실시간 고점 추적 ─────────────────────────────────────────────
    def _advance_peak(self, symbol: str, pos: dict, price: Decimal):
        """소켓 체결가로 peak_high 를 갱신하고 트레일 라인을 재계산한다.

        DB 쓰기는 하지 않는다(장 종료 시 flush_peaks 가 일괄 저장).
        라인 산출식은 daily 평가와 동일하게 모드 전략의 _trail_line_of 에 위임한다.
        """
        if not self.strategy:
            return
        s = self.strategy.strategy          # 운용모드로 결정된 전략 인스턴스
        if not getattr(s, "use_trailing", True):
            return

        entry = float(pos.get("entry_price") or 0)
        if entry <= 0:
            return
        p = float(price)

        with self._lock:
            prev_peak = float(pos.get("peak_high") or entry)
            if p <= prev_peak:
                return                       # 고점 갱신 없음 → 재계산 불필요
            pos["peak_high"] = p
            self._peak_dirty.add(symbol)

            # 활성화 게이트: 고점수익이 trail_activate_pct 이상일 때만 라인을 세운다.
            if (p - entry) / entry < getattr(s, "trail_activate_pct", 0.08):
                return

            # ATR 은 daily 평가가 남긴 last_atr 우선, 없으면 진입 시점 ATR.
            atr = float(pos.get("last_atr") or pos.get("entry_atr") or 0)
            line, src = s._trail_line_of(entry, p, atr)
            pos["trail_line"] = round(line, 2)

        self._log_peak(symbol, p, pos.get("trail_line"), src)

    def _log_peak(self, symbol: str, peak: float, line, src: str):
        """고점 갱신 로그 — 틱마다 찍으면 폭주하므로 종목당 30초 1회."""
        now = time.time()
        if now < self._peak_log.get(symbol, 0):
            return
        self._peak_log[symbol] = now + 30
        self.wlog.info("[매도] %s 고점 갱신 %s → trail=%s (%s)", symbol, peak, line, src)

    def flush_peaks(self, tag: str = ""):
        """장중 메모리에 쌓인 peak_high / trail_line 을 DB 에 저장.

        세션 종료 후 1회 호출(main.py cron). 다음날 reload_positions 가 이 값을
        다시 읽어 감시를 이어간다. 호출 시점 이후의 틱은 다시 dirty 로 쌓인다.
        """
        with self._lock:
            targets = list(self._peak_dirty)
            self._peak_dirty.clear()

        saved = 0
        for code in targets:
            pos = self.positions.get(code)
            if not pos:
                continue
            state = {"peak_high": round(float(pos.get("peak_high") or 0), 4)}
            if pos.get("trail_line") is not None:
                state["trail_line"] = pos["trail_line"]
            try:
                self.repo.update_position_state(self.cfg.user_id, code, state)
                saved += 1
            except Exception as e:  # noqa: BLE001
                self.wlog.warn("[매도] %s 고점 저장 실패: %s", code, e)
                with self._lock:
                    self._peak_dirty.add(code)   # 다음 flush 에서 재시도
        if saved:
            self.wlog.info("[매도] 고점 flush%s: %d종목 저장", f"({tag})" if tag else "", saved)

    # ── 모드별 훅 ────────────────────────────────────────────────────
    @abstractmethod
    def hit_line(self, pos: dict, price: Decimal) -> str | None:
        """이 틱에서 팔아야 하는가. 사유 문자열을 반환하면 매도, None 이면 보유 유지.

        **모드별로 갈리는 유일한 판정 지점**이다. 반환한 사유는 그대로
        trade_worker_position.exit_reason 과 trade_log 에 적재된다.
        """

    def sell_qty(self, pos: dict, actual) -> Decimal:
        """이번에 팔 수량. 기본은 보유 전량(DB 와 실계좌 중 작은 쪽)."""
        db_qty = _toDecimal(pos.get("hold_qty")) or Decimal(0)
        return db_qty if actual is None else min(db_qty, actual)

    def _resolve_sell_qty(self, pos: dict, actual, manual: dict | None) -> Decimal:
        """매도 수기등록(티어)이 있으면 그 수량을 적용하고, 없으면 모드 기본
        정책(sell_qty, 기본 전량)을 그대로 쓴다.

        수량 산출은 두 가지 방식이 있다:
          1) base_qty(등록 시점 보유수량 스냅샷)가 있으면 base_qty × qty_ratio 의
             **절대수량**으로 고정한다 — 종목당 여러 티어(사다리 매도)를 등록해도
             먼저 체결된 티어가 실보유를 줄여놔서 다음 티어의 비율 기준이 함께
             줄어드는 문제가 없다(2026-08-21 다건화). 단 실제/DB 보유수량을
             넘겨 팔 수는 없으니 그 값으로 상한을 씌운다.
          2) base_qty 가 없는(구 단일슬롯 시절 등록된) 행은 매도 시점 실보유
             대비 비율로 계산하는 기존 방식으로 폴백한다.
        """
        if manual is None:
            return self.sell_qty(pos, actual)
        db_qty = _toDecimal(pos.get("hold_qty")) or Decimal(0)
        base = db_qty if actual is None else min(db_qty, actual)
        ratio = _toDecimal(manual.get("qty_ratio"))
        if ratio is None or ratio <= 0:
            ratio = Decimal("1")
        base_qty = _toDecimal(manual.get("base_qty"))
        if base_qty is not None and base_qty > 0:
            qty = (base_qty * ratio).quantize(Decimal("1"), rounding=ROUND_DOWN)
            qty = min(qty, base)   # 실제/DB 보유수량 상한 — 초과 매도 방지
        else:
            qty = (base * ratio).quantize(Decimal("1"), rounding=ROUND_DOWN)
        return qty

    # ── 일별 전략 평가 (모드 전략) ───────────────────────
    def refresh_positions(self):
        """HOLDING 포지션마다 모드 전략으로 라인/액션 재계산 → DB 갱신.
        일봉 신호(OBV 데드크로스·타임스탑 등)로 SELL 판정되면 개장 시 즉시 매도.
        realtime stop/target/trail 라인도 이 값으로 갱신됨."""
        if not self.strategy:
            return
        for code, pos in list(self.positions.items()):
            if code in self._sold or code in self._disabled:
                continue
            if self._manual_sells.get(code):
                # 매도 수기등록 종목(티어 1개 이상) — 모드 전략의 일봉 신호(OBV
                # 데드크로스·타임스탑 등)도 보지 않는다. 실시간 지정가 감시(on_price)만
                # 이 종목을 판정한다.
                prices = ", ".join(str(t.get("sell_price")) for t in self._manual_sells[code])
                self.wlog.info("[매도] %s 수기등록됨(@[%s]) → 모드 전략 평가 skip", code, prices)
                continue
            try:
                result, state = self.strategy.evaluate(pos)
            except Exception as e:  # noqa: BLE001
                self.wlog.warn("[매도] %s 전략 평가 실패: %s", code, e)
                continue
            if state is None:
                self.wlog.warn("[매도] %s 데이터 부족 → 평가 skip", code)
                continue
            # DB 라인/상태 갱신 + 메모리 포지션 갱신(realtime 감시에 반영)
            self.repo.update_position_state(self.cfg.user_id, code, state)
            with self._lock:
                pos.update({
                    "stop_price": state.get("stop_price"),
                    "target_price": state.get("target_price"),
                    "trail_line": state.get("trail_line"),
                    "bars_held": state.get("bars_held"),
                    "peak_high": state.get("peak_high"),
                    # 장중 _advance_peak 이 라인 재계산에 쓸 ATR
                    "last_atr": state.get("last_atr"),
                })
                # evaluate 가 DB 와 메모리를 방금 일치시켰다 → dirty 해제
                self._peak_dirty.discard(code)
            action = (result or {}).get("action_type", "HOLD")
            self.wlog.info("[매도] %s 평가: %s (stop=%s target=%s trail=%s bars=%s)",
                           code, action, state.get("stop_price"), state.get("target_price"),
                           state.get("trail_line"), state.get("bars_held"))
            if action != "HOLD":
                nxt = (pos.get("nxt_flag") == "Y")
                sess = self._session(pos)
                if not sess.tradable:
                    self.wlog.info("[매도] %s 일봉신호(%s) 이지만 %s → 주문 보류", code, action, sess.name)
                    continue
                try:
                    price = self.broker.current_price(code, nxt=nxt)
                except Exception as e:  # noqa: BLE001
                    self.wlog.warn("[매도] %s 개장 시세 실패: %s", code, e)
                    price = _toDecimal(state.get("target_price")) or Decimal(0)
                self._do_sell(code, pos, price, action, sess)

    # ── 실제 보유수량 조회 ───────────────────────────────────────────
    def _actual_qty(self, symbol: str):
        """실제 계좌 보유수량. 조회 실패 시 None, 목록에 없으면 0."""
        holdings = self.broker.account_holdings()
        if holdings is None:
            return None
        for h in holdings:
            if h.get("symbol") == symbol:
                return Decimal(str(h.get("qty") or 0))
        return Decimal(0)

    def _register_fail(self, symbol: str, msg: str):
        """매도 실패 → 쿨다운 설정. 연속 실패가 임계 도달 시 자동 비활성."""
        self._cooldown[symbol] = time.time() + self.cfg.sell_retry_cooldown_sec
        c = self._fail_count.get(symbol, 0) + 1
        self._fail_count[symbol] = c
        self.wlog.warn("[매도] %s 실패(%d회) → %ds 쿨다운: %s",
                       symbol, c, self.cfg.sell_retry_cooldown_sec, msg)
        if c >= self.cfg.sell_max_fails:
            self._disabled.add(symbol)
            self.wlog.warn("[매도] %s 연속 %d회 실패 → 자동 비활성(수동 확인 필요)", symbol, c)
            if self.notifier:
                self.notifier.send("⚠ 매도 실패 경보", f"{symbol} 매도 {c}회 실패로 자동 비활성됨")

    # ── 매도 실행 ────────────────────────────────────────────────────
    def _do_sell(self, symbol: str, pos: dict, price: Decimal, reason: str, sess=None,
                manual: dict | None = None):
        # manual: MANUAL_SELL 이면 이번에 체결하는 **단일 티어**(trade_worker_manual_sell
        # 행 1건, 종목당 여러 티어 중 하나) — id/sell_price/qty_ratio/base_qty 를 담고 있다.
        # 동시성 가드: 소켓 콜백이 여러 틱 동시 진입해도 종목당 1건만 진행.
        with self._lock:
            if symbol in self._sold or symbol in self._inflight or symbol in self._disabled:
                return
            cd = self._cooldown.get(symbol)
            if cd and time.time() < cd:
                return
            self._inflight.add(symbol)
        try:
            # ── 실제 보유수량으로 매도량 보정(‘주문가능수량 초과’ 방지) ──
            actual = self._actual_qty(symbol)
            if actual is not None and actual <= 0:
                # 실제 보유 없음 = 이미 청산됨 → 포지션 종료(정리)
                self.repo.close_position(self.cfg.user_id, symbol, price, Decimal(0), "EXTERNAL_CLOSED")
                self.positions.pop(symbol, None)
                self._sold.add(symbol)
                self._unsubscribe(symbol)   # 보유 종료 → 실시간 감시 비활성
                self.wlog.warn("[매도] %s 실제 보유 0 → 청산된 것으로 간주하고 정리", symbol)
                return
            qty = self._resolve_sell_qty(pos, actual, manual)   # 수기등록 비율 or 모드 기본(전량)
            if qty <= 0:
                self.wlog.warn("[매도] %s 매도수량 0 (hold=%s actual=%s) → skip",
                               symbol, pos.get("hold_qty"), actual)
                self._register_fail(symbol, "매도수량 0")
                return

            sess = sess or self._session(pos)
            if not sess.tradable:
                self.wlog.info("[매도] %s %s → 주문 보류(실패로 세지 않음)", symbol, sess.name)
                return

            # 지정가 세션(NXT 프리/애프터마켓)은 시장가가 없다.
            # 손절/익절은 체결 속도가 생명이므로 체결가보다 한 틱 아래로 걸어 즉시 체결을 유도한다.
            order_px = price
            if sess.limit_only:
                order_px = self.broker.align_price(
                    price * (1 - Decimal(str(self.cfg.sell_limit_slip_pct)) / 100))
                if order_px <= 0:
                    self._register_fail(symbol, f"지정가 산출 실패(price={price})")
                    return
                self.wlog.info("[매도] %s %s 지정가=%s (체결가=%s -%s%%)",
                               symbol, sess.name, order_px, price, self.cfg.sell_limit_slip_pct)
            try:
                order = self.broker.order_in_session("SELL", symbol, qty, order_px, sess)
            except Exception as e:  # noqa: BLE001  (KIS API 오류·수량초과·rate limit 등)
                self._register_fail(symbol, f"주문 예외: {e}")
                return

            # 주문 즉시 추적 등록(아직 armed=False → 아래 동기 처리와 이중 계상 안 됨)
            self.broker.register_watch(order, self._on_late_fill)
            res = self.broker.wait_fill(order)

            # 체결 실패/미체결/거부 → 쿨다운(폭주 방지), 보유 유지
            if res.status == "REJECTED" or res.filled_qty <= 0:
                self.broker.unregister_watch(res.order_no)
                self._register_fail(symbol, f"status={res.status} reason={res.reason}")
                return

            fill_px = res.avg_price or price
            proceeds = fill_px * res.filled_qty
            computed_balance = self.repo.get_wallet_balance(self.cfg.user_id) + proceeds

            # 부분체결이면 체결분만 차감하고 **보유·감시를 유지**한다.
            # (이전에는 1주만 체결돼도 close_position + unsubscribe 로 전량 청산 처리해서
            #  잔여 보유분이 감시에서 이탈했다. reduce_position 이 잔량을 돌려준다.)
            remain = self.repo.reduce_position(self.cfg.user_id, symbol, fill_px,
                                               res.filled_qty, reason)
            final_balance = reconcile_wallet(self.broker, self.repo, self.cfg.user_id,
                                             computed=computed_balance,
                                             sync=self.cfg.sync_wallet_on_trade, tag="매도")
            self.repo.insert_trade_log(self.cfg.user_id, symbol, "SELL", fill_px, res.filled_qty,
                                       final_balance, note=f"{reason}/{res.status}")
            if self.notifier:
                self.notifier.trade("SELL", pos.get("stock_name") or "", symbol,
                                    res.filled_qty, fill_px, final_balance,
                                    note=f"{reason} · {res.status}"
                                         + (f" · 잔량 {remain}주" if remain > 0 else ""))

            # ⚠ remain(=이 종목 전체 보유수량)과 "이 주문(=이 티어)이 다 팔렸는가"는
            # 다른 질문이다 — 사다리 매도에서는 다른 티어가 아직 보유분을 들고 있어
            # remain>0 이어도 지금 이 주문 자체는 전량 체결됐을 수 있다. 포지션(종목)
            # 정리는 remain 으로, 수기등록 **티어** 완료는 이 주문의 체결 완료 여부
            # (armed=False, 아래 arm_watch 결과)로 따로 판단한다.
            if remain > 0:
                # 잔량 보유 → 감시 유지. _sold 로 막지 않는다(다음 라인 돌파에 다시 매도).
                with self._lock:
                    p = self.positions.get(symbol)
                    if p is not None:
                        p["hold_qty"] = remain
                self.wlog.info("[매도] 부분체결 %s qty=%s @~%s 잔량=%s주 → 감시 유지 (%s/%s)",
                               symbol, res.filled_qty, fill_px, remain, reason, res.status)
            else:
                self.positions.pop(symbol, None)
                self._unsubscribe(symbol)   # 전량 청산 → 실시간 감시 비활성
                self._sold.add(symbol)
                self.wlog.info("[매도] 완료 %s qty=%s @~%s 잔고=%s (%s/%s)",
                               symbol, res.filled_qty, fill_px, final_balance, reason, res.status)

            self._fail_count.pop(symbol, None)
            self._cooldown.pop(symbol, None)

            # 동기 처리 완료 → 추적 개시. 미체결 잔여 **주문**이 있으면 늦은 체결이 콜백으로 온다.
            # arm_watch 가 False 를 반환하면 이 주문은 이미 동기 창 안에서 전량 체결됐다는
            # 뜻 — 그 즉시 이 티어를 완료 처리한다(종목 전체 remain 과 무관).
            if self.broker.arm_watch(res):
                self._pending_reason[res.order_no] = reason
                if manual is not None:
                    self._pending_manual_id[res.order_no] = manual.get("id")
                # 잔여 주문이 아직 살아있는데 다음 틱에서 또 팔면 '주문가능수량 초과'가 난다.
                # (계좌 보유수량은 매도 주문을 걸어둬도 줄지 않지만 주문가능수량은 줄어든다)
                # 쿨다운을 걸어 살아있는 주문이 체결될 시간을 준다.
                self._cooldown[symbol] = time.time() + self.cfg.sell_retry_cooldown_sec
                self.wlog.info("[매도] %s 미체결 주문 %s주 체결 대기(이벤트 추적) · %ds 재주문 보류",
                               symbol, res.qty - res.filled_qty, self.cfg.sell_retry_cooldown_sec)
            else:
                self._complete_manual_if_needed(symbol, reason, fill_px, res.filled_qty,
                                                manual_id=(manual or {}).get("id"))
        except Exception as e:  # noqa: BLE001  (예상 밖 오류도 폭주 없이 쿨다운)
            self._register_fail(symbol, f"예외: {e}")
        finally:
            self._inflight.discard(symbol)

    # ── 동기 창 밖 체결(잔여 매도주문) 반영 ──────────────────────────
    def _on_late_fill(self, ev):
        """매도 주문의 미체결 잔량이 뒤늦게 체결됐을 때 소켓 스레드에서 호출된다.

        ev.delta_qty 만 차감한다(ev.filled_qty 는 누적이라 그대로 쓰면 이중 차감).
        차감 결과 잔량이 0 이 되면 그때 비로소 포지션 종료 + 감시 해제한다.
        """
        uid = self.cfg.user_id
        symbol = ev.symbol
        if ev.rejected:
            self.wlog.warn("[매도] %s 잔여주문 거부 order=%s reason=%s", symbol, ev.order_no, ev.reason)
            self._pending_reason.pop(ev.order_no, None)
            self._pending_manual_id.pop(ev.order_no, None)
            return
        if ev.delta_qty <= 0:
            return
        reason = self._pending_reason.get(ev.order_no, "LATE_FILL")
        manual_id = self._pending_manual_id.get(ev.order_no)
        try:
            remain = self.repo.reduce_position(uid, symbol, ev.last_price, ev.delta_qty, reason)
            balance = reconcile_wallet(self.broker, self.repo, uid,
                                       sync=self.cfg.sync_wallet_on_trade, tag="매도잔량")
            self.repo.insert_trade_log(uid, symbol, "SELL", ev.last_price, ev.delta_qty, balance,
                                       note=f"{reason}/late {ev.filled_qty}/{ev.order_qty}")
            # remain(종목 전체 잔량)과 이 주문(티어)의 완료 여부(ev.complete)는 별개다 —
            # 사다리 매도에서는 다른 티어의 보유분이 남아 remain>0 이어도 이 주문은
            # 이번 통보로 전량 체결(ev.complete)됐을 수 있다.
            if remain > 0:
                with self._lock:
                    p = self.positions.get(symbol)
                    if p is not None:
                        p["hold_qty"] = remain
                self.wlog.info("[매도] %s 잔량체결 -%s주 @%s → 보유 %s주 유지",
                               symbol, ev.delta_qty, ev.last_price, remain)
            else:
                with self._lock:
                    self.positions.pop(symbol, None)
                self._unsubscribe(symbol)
                self._sold.add(symbol)
                self._cooldown.pop(symbol, None)
                self.wlog.info("[매도] %s 잔량체결로 전량 청산 완료 @%s 잔고=%s",
                               symbol, ev.last_price, balance)
            if ev.complete:
                self._pending_reason.pop(ev.order_no, None)
                self._pending_manual_id.pop(ev.order_no, None)
                self._complete_manual_if_needed(symbol, reason, ev.last_price, ev.delta_qty,
                                                manual_id=manual_id)
        except Exception as e:  # noqa: BLE001
            self.wlog.warn("[매도] %s 잔량체결 반영 실패: %s", symbol, e)

    def _on_execution(self, execution):
        # 실시간 체결통보 원본 로깅 훅(모든 통보 — worker 주문/타채널 주문 구분 없이).
        # 실제 포지션·잔고 반영은 broker 가 주문번호로 라우팅해 _on_late_fill 로 보낸다.
        try:
            self.wlog.info("[체결통보] %s executed_qty=%s price=%s",
                           getattr(execution, "symbol", "?"),
                           getattr(execution, "executed_qty", "?"),
                           getattr(execution, "price", "?"))
        except Exception:  # noqa: BLE001
            pass
