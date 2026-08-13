"""
M1 (추천 1순위) 매수 — 20:00 배치가 만든 trade_buy_target_stock 의 1순위를 익일 매수.

BaseBuyExecutor 에서 갈리는 지점은 **후보 선정 하나**뿐이다.
시세·수량·주문·체결추적·포지션반영은 전부 베이스가 처리한다.

로직은 docs_buy_target_sim_spec.md §3 기준이며, 리팩터링 전 BuyExecutor.run() 의
후보 선정 블록을 **동작 변경 없이** 그대로 옮긴 것이다.
"""
from decimal import Decimal

from app.trade_worker.buy_executor import BaseBuyExecutor, BuyCandidate
from app.trade_worker.repository import describe_buy_order


class BuyExecutor1(BaseBuyExecutor):
    """M1 : 추천 1순위 자동매매."""

    MODE_CODE = "M1"

    def supports_premarket(self) -> bool:
        """NXT 프리마켓(08:00) 선매수 라운드를 쓴다."""
        return True

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
        # 직전 영업일을 KIS 휴장일 API로 동적 산출해 하한으로 사용(공휴일·연휴 반영).
        # 조회 실패(None)면 repo 가 요일 heuristic 으로 fallback.
        floor_ymd = self.broker.prev_trading_day()
        ymd = self.repo.get_latest_buy_target_ymd(min_ymd=floor_ymd)
        if not ymd:
            self.wlog.info("[매수] 매수타겟 없음")
            return []

        # 정렬 1순위 = 매수 종목이므로, 설정값이 아니라 **실제 적용된** 정렬을 남긴다
        # (오타·미지원 필드는 repo 가 조용히 걸러내고 기본값으로 되돌리기 때문).
        order_spec = self._buy_order_spec()
        targets = self.repo.get_buy_targets(ymd, order_spec=order_spec)
        self.wlog.info("[매수] 타겟 %d건 (ymd=%s · 정렬=%s)",
                       len(targets), ymd, describe_buy_order(order_spec))

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

    @staticmethod
    def _to_candidate(tgt: dict, ymd: str) -> BuyCandidate:
        close = tgt.get("close")
        return BuyCandidate(
            code=tgt["stock_code"],
            name=tgt.get("stock_name") or "",
            nxt=(tgt.get("nxt_flag") == "Y"),
            ref_close=Decimal(str(close)) if close else None,
            log_note=f"buy target ymd={ymd} rate={tgt.get('rate')}",
            notify_note=f"score={tgt.get('score')}",
        )
