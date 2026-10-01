"""
M1 (추천매수) 매수 — 20:00 배치가 만든 trade_buy_target_stock 의 1순위를 익일 매수.

BaseBuyExecutor 에서 갈리는 지점은 **후보 선정 하나**뿐이다.
시세·수량·주문·체결추적·포지션반영은 전부 베이스가 처리한다.

로직은 docs_buy_target_sim_spec.md §3 기준이며, 리팩터링 전 BuyExecutor.run() 의
후보 선정 블록을 **동작 변경 없이** 그대로 옮긴 것이다.

최우선타겟(Home.vue select)은 "1순위로 시도"가 아니라 **"그 날 꼭 산다"** 다
(2026-10-01 사용자 결정). 그래서 일반 후보에 걸리는 두 관문을 비켜간다:
  1) 시가갭 게이트 면제 — 갭 크기와 무관하게 매수한다.
  2) 1포지션 원칙 예외   — 보유 종목이 있어도 매수한다.
단 2)는 **최우선타겟 그 종목에만** 적용한다. 차단을 풀어둔 채 대신매수 fallthrough
까지 허용하면 최우선타겟이 실패했을 때 사용자가 지정하지도 않은 종목으로 2번째
포지션이 열린다. 그래서 예외로 통과한 라운드는 후보를 그 종목 하나로 좁힌다.
소비 정책은 그대로 "정규장 라운드 종료 시 1회성"이다(당일만 유효).
"""
from decimal import Decimal
from typing import Optional

from app.trade_worker.buy_executor import BaseBuyExecutor, BuyCandidate
from app.trade_worker.repository import describe_buy_order


class BuyExecutor1(BaseBuyExecutor):
    """M1 : 추천매수 자동매매."""

    MODE_CODE = "M1"

    # 장 시작 갭(현재가 vs 전일종가) 차단 임계값. 2026-09 세션 리서치 반영 —
    # 갭 그 자체를 게이트로 신설. 0%로 두면 정상 호가단위 노이즈만으로도 거의
    # 매번 걸리므로, "유의미한 갭"과 "체결 틱 노이즈"를 가르는 최소값을 둔다.
    #   ※ 최우선타겟은 이 게이트를 타지 않는다(_resolve_price 참고).
    GAP_BLOCK_PCT = Decimal("0.01")   # 1%

    def __init__(self, cfg, broker, repo, notifier=None, strategy=None):
        super().__init__(cfg, broker, repo, notifier, strategy)
        # ── 라운드 단위 상태 ────────────────────────────────────────────
        #   worker 는 한 프로세스가 하루 종일 살아 있고, **같은 인스턴스**로 08:00
        #   프리마켓과 09:00 정규장 두 라운드를 돈다. 그래서 라운드가 끝날 때
        #   반드시 비워야 한다(_finalize_round) — 안 비우면 09:00 라운드가 한 시간
        #   전에 조회한 타겟과 판정을 그대로 재사용한다.
        self._targets_cache: Optional[tuple] = None   # (ymd, targets) 라운드당 1회 조회
        self._priority_code: Optional[str] = None     # 이번 라운드의 최우선타겟 종목코드
        self._priority_only = False                   # 1포지션 예외로 통과한 라운드인지

    def supports_premarket(self) -> bool:
        """NXT 프리마켓(08:00) 선매수 라운드를 쓴다."""
        return True

    # ── 1포지션 원칙 + 최우선타겟 예외 ───────────────────────────────
    def allow_buy(self) -> bool:
        """베이스의 1포지션 판정에 **최우선타겟 예외**를 더한다.

        사용자가 지정한 종목은 보유분이 있어도 산다. 다만 예외를 적용하기 전에
        세 가지를 확인한다 — 하나라도 어긋나면 기존처럼 차단한다:
          · 지정이 실제로 대기 중인가
          · 그 종목을 **이미 보유 중이 아닌가** — 08:00 프리마켓에서 체결된 뒤
            09:00 에 같은 종목을 한 번 더 사는 이중 매수를 막는 핵심 가드다.
          · 오늘 매수타겟 목록에 들어 있는가 — 없으면 애초에 살 수 없으니
            차단을 풀어줄 이유가 없다(풀어주면 대신매수로 엉뚱한 2번째 포지션이 열린다).
        """
        if super().allow_buy():
            return True

        code = self.repo.get_priority_target(self.cfg.user_id)
        if not code:
            return False

        held = {p.get("stock_code") for p in self.repo.get_holding_positions(self.cfg.user_id)}
        if code in held:
            self.wlog.info("[매수] 최우선타겟 %s 은 이미 보유 중 → 1포지션 예외 미적용", code)
            return False

        _ymd, targets = self._round_targets()
        if not any(t["stock_code"] == code for t in targets):
            self.wlog.info("[매수] 최우선타겟 %s 가 오늘 매수타겟 목록에 없음 → 1포지션 차단 유지",
                           code)
            return False

        self._priority_only = True
        self.wlog.warn("[매수] 1포지션 차단 상태이지만 최우선타겟 %s 지정됨 → "
                       "이 종목 단독으로 매수 진행(사용자 지정 예외)", code)
        return True

    def _round_targets(self) -> tuple:
        """이번 라운드의 (ymd, 정렬된 타겟). allow_buy 와 pick_candidates 가 공유한다.

        prev_trading_day() 가 KIS 호출이라 라운드당 한 번만 조회한다
        (예외 판정 때문에 allow_buy 가 먼저 타겟을 보게 됐다).
        """
        if self._targets_cache is not None:
            return self._targets_cache

        # 직전 영업일을 KIS 휴장일 API로 동적 산출해 하한으로 사용(공휴일·연휴 반영).
        # 조회 실패(None)면 repo 가 요일 heuristic 으로 fallback.
        floor_ymd = self.broker.prev_trading_day()
        ymd = self.repo.get_latest_buy_target_ymd(min_ymd=floor_ymd)
        if not ymd:
            self._targets_cache = (None, [])
        else:
            self._targets_cache = (
                ymd, self.repo.get_buy_targets(ymd, order_spec=self._buy_order_spec()))
        return self._targets_cache

    def _resolve_price(self, cand: BuyCandidate, premarket: bool) -> Optional[Decimal]:
        """베이스 가격 조회 + 갭 게이트.

        프리마켓 라운드는 지정가 자체가 '전일종가×(1+슬리피지%)'라 갭 개념이 없다
        (BaseBuyExecutor._resolve_price 참고) — 정규장(09:00) 라운드에서만 적용한다.
        전일종가(ref_close)가 없으면(신규 편입 등) 갭을 판정할 수 없으므로 통과시킨다.
        """
        price = super()._resolve_price(cand, premarket)
        if price is None or premarket:
            return price

        ref_close = cand.ref_close
        if not ref_close or Decimal(str(ref_close)) <= 0:
            return price

        ref_close = Decimal(str(ref_close))
        gap_pct = abs(price - ref_close) / ref_close

        # 최우선타겟은 갭 크기와 무관하게 통과시킨다(2026-10-01 사용자 결정 — 한도 없음).
        # 게이트를 건너뛰더라도 **갭 값은 반드시 로그에 남긴다**: 상한가 근처 갭에
        # 시장가로 진입한 날 "왜 이 가격에 샀나"를 사후에 추적할 수 있어야 한다.
        if cand.priority:
            if gap_pct > self.GAP_BLOCK_PCT:
                self.wlog.warn(
                    "[매수] %s 최우선타겟 → 시가갭 %.2f%%(전일종가=%s, 현재가=%s)로 "
                    "허용치 %.1f%% 초과이지만 사용자 지정이라 매수 진행",
                    cand.code, float(gap_pct * 100), ref_close, price,
                    float(self.GAP_BLOCK_PCT * 100),
                )
            return price

        if gap_pct > self.GAP_BLOCK_PCT:
            self.wlog.info(
                "[매수] %s 시가갭 %.2f%%(전일종가=%s, 현재가=%s) > 허용치 %.1f%% → skip",
                cand.code, float(gap_pct * 100), ref_close, price, float(self.GAP_BLOCK_PCT * 100),
            )
            return None
        return price

    def _buy_order_spec(self) -> str | None:
        """유저 매수타겟 정렬 스펙(user_options.s1_buy_order).

        user_meta 는 SellStrategy 가 이미 들고 있어(UserService.get_user_options)
        재조회하지 않는다. strategy 미주입(단위테스트 등)이면 None → repo 기본값.
        """
        meta = getattr(self.strategy, "user_meta", None)
        return getattr(meta, "s1_buy_order", None) if meta else None

    def pick_candidates(self, premarket: bool) -> list[BuyCandidate]:
        """전날 매수타겟을 유저 정렬 기준으로 정렬해 반환.

        premarket=True 면 **정렬 1위가 NXT 대상일 때만** 그 1건을 반환한다.
        후보를 훑어 내려가면 score 1위(KRX 전용)를 두고 하위 종목을 사버리고,
        1포지션 원칙 때문에 09:00 에 1위를 살 기회가 사라진다. 프리마켓 라운드는
        '1위가 마침 NXT면 일찍 잡는다'는 보너스로만 동작해야 한다.
        """
        ymd, targets = self._round_targets()
        if not ymd:
            self.wlog.info("[매수] 매수타겟 없음")
            return []

        # 정렬 1순위 = 매수 종목이므로, 설정값이 아니라 **실제 적용된** 정렬을 남긴다
        # (오타·미지원 필드는 repo 가 조용히 걸러내고 기본값으로 되돌리기 때문).
        targets = self._promote_priority(targets)
        self.wlog.info("[매수] 타겟 %d건 (ymd=%s · 정렬=%s)",
                       len(targets), ymd, describe_buy_order(self._buy_order_spec()))

        # 1포지션 예외로 통과한 라운드는 **최우선타겟 단독**으로 좁힌다.
        # 대신매수까지 허용하면 지정하지 않은 종목으로 2번째 포지션이 열린다.
        if self._priority_only:
            targets = [t for t in targets if t["stock_code"] == self._priority_code]
            self.wlog.info("[매수] 1포지션 예외 라운드 → 최우선타겟 %s 단독 후보(대신매수 없음)",
                           self._priority_code)

        if premarket:
            if not targets:
                self.wlog.info("[매수] 매수타겟 없음")
                return []
            top = targets[0]
            if top.get("nxt_flag") != "Y":
                self.wlog.info("[매수] 1위 %s(%s) NXT 미대상(nxt_flag=%s) → 프리마켓 skip, 09:00 대기",
                               top.get("stock_name"), top["stock_code"], top.get("nxt_flag"))
                return []
            targets = [top]

        return [self._to_candidate(t, ymd) for t in targets]

    def _promote_priority(self, targets: list[dict]) -> list[dict]:
        """Home.vue "최우선타겟" select 로 사용자가 지정한 종목이 오늘 매수타겟
        목록에 있으면 1순위로 승격시킨다(그 외 순서는 그대로 유지).

        여기서는 순서만 바꾸고 상태는 건드리지 않는다 — 프리마켓(08:00)·정규장(09:00)
        두 라운드가 같은 지정값을 봐야 하기 때문. 실제 소비(1회성 null화)는 정규장
        라운드가 끝날 때 _finalize_round 에서 한 번만 한다.
        """
        self._priority_code = None
        priority_code = self.repo.get_priority_target(self.cfg.user_id)
        if not priority_code:
            return targets

        idx = next((i for i, t in enumerate(targets) if t["stock_code"] == priority_code), None)
        if idx is None:
            self.wlog.info("[매수] 최우선타겟 %s 가 오늘 매수타겟 목록에 없음 → 무시", priority_code)
            return targets

        # 여기서 기록한 코드가 _to_candidate 의 priority 플래그 → 갭 게이트 면제로 이어진다.
        self._priority_code = priority_code
        promoted = targets[idx]
        self.wlog.info("[매수] 최우선타겟 %s(%s) 을 1순위로 승격 · 시가갭 게이트 면제",
                       promoted.get("stock_name"), priority_code)
        return [promoted] + targets[:idx] + targets[idx + 1:]

    def _finalize_round(self, premarket: bool):
        """정규장 라운드가 끝나면(체결 성공/후보 없음/전량 스킵 등 무관) 최우선타겟을
        1회성으로 소비(null화)한다. 프리마켓 라운드는 'NXT 대상이면 일찍 잡는' 보너스
        라운드일 뿐 최종 판정이 아니므로 여기서 소비하지 않는다 — 09:00 정규장에서
        다시 한 번 같은 지정값을 볼 수 있어야 한다.

        라운드 상태(타겟 캐시·최우선타겟 판정)는 **프리마켓이든 정규장이든** 비운다.
        08:00 캐시가 남으면 09:00 라운드가 한 시간 전 타겟·판정을 재사용한다."""
        try:
            if premarket:
                return
            try:
                if self.repo.clear_priority_target(self.cfg.user_id):
                    self.wlog.info("[매수] 최우선타겟 1회성 소비 완료 → 초기화")
            except Exception as e:  # noqa: BLE001
                self.wlog.warn("[매수] 최우선타겟 초기화 실패: %s", e)
        finally:
            self._targets_cache = None
            self._priority_code = None
            self._priority_only = False

    def _to_candidate(self, tgt: dict, ymd: str) -> BuyCandidate:
        close = tgt.get("close")
        code = tgt["stock_code"]
        return BuyCandidate(
            code=code,
            name=tgt.get("stock_name") or "",
            nxt=(tgt.get("nxt_flag") == "Y"),
            ref_close=Decimal(str(close)) if close else None,
            priority=(code == self._priority_code),
            log_note=f"buy target ymd={ymd} rate={tgt.get('rate')}",
            notify_note=f"score={tgt.get('score')}",
        )
