-- ============================================================================
-- stock/003_final_strategy_apply.sql  (2026-11-16)
--
-- ⚠ 비밀상회(private 고객) 실전 자동매매 설정 — 사용자(대표) 승인 없이 이 값들을 바꾸거나 되돌리지 말 것.
-- 연구로 확정한 매매 전략을 트레이딩 유저 1·2·3·4·6 에게 똑같이 적용한다(5번은 대상 아님).
--   연구 근거: py-stock-batch/app/test/bt_final_*.py, 매매 장부 bt_reco_cache/final/양봉_매매장부_2024-2026.xlsx
--
-- [매도] user_option_reco (워커가 라운드마다 읽음 — 재시작 없이 반영)
--   손절 -8% · 익절 +30% · 트레일링 켬(고점 +8% 부터, 고점 − ATR 2.5배 단독 — 고점 대비 %·수익 반납·피보는 끔)
--   타임스탑 7거래일, 연장 없음 · 매수 순서 = 종합순위(2파, 거래량 배수 순) 1위부터
--   ※ 연구의 '상승 추세선 이탈 매도'는 워커에 아직 없다(연구에서 130건 중 1~4건만 발동해 영향이 작았다).
--   ※ 갭 차단(gap_block_pct)은 건드리지 않는다(기본 ±2% 그대로).
-- [매수] master_codes stock/setting/batch (배치가 매 실행마다 읽음)
--   WAVE2_MIN_VOL_PCT  = 0.6667 : 2파 신호 중 그날 변동성 상위 1/3 만 순위를 매긴다
--   WAVE2_MIN_BREADTH  = 0.40   : 시장 폭(사전 필터 종목 중 종가 > 20일선 비율) 40% 미만인 날은 순위 없음 = 그날 신호 매수 쉼
--   → 배치 코드(StockBuyCheckJob 실전 게이트)가 배포돼야 효과가 있다. 배포 전에는 이 두 행을 읽는 코드가 없어 무시된다.
--
-- 적용 순서: ① 백업 → ② 이 SQL 의 UPDATE·INSERT → ③ 배치 배포(실전 게이트 코드) — 워커는 재시작 불필요(설정 폴링)
-- 확인:
--   SELECT user_id, stop_loss_pct, take_profit_pct, use_trailing, trail_activate_pct, k_trail_atr, trail_drawdown_pct,
--          trail_giveback_pct, trail_fib_use, trail_dual, max_hold_bars, max_hold_bars_hard, time_stop_extend, buy_order
--     FROM stock.user_option_reco WHERE user_id IN (1,2,3,4,6);
--   SELECT code, `desc` FROM stock.master_codes WHERE `system`='stock' AND source='setting' AND category='batch';
-- 되돌리기:
--   UPDATE stock.user_option_reco r JOIN stock.user_option_reco_bak_20261116 b ON b.user_id = r.user_id
--      SET r.stop_loss_pct = b.stop_loss_pct, r.take_profit_pct = b.take_profit_pct, r.use_trailing = b.use_trailing,
--          r.trail_activate_pct = b.trail_activate_pct, r.k_trail_atr = b.k_trail_atr, r.trail_drawdown_pct = b.trail_drawdown_pct,
--          r.trail_giveback_pct = b.trail_giveback_pct, r.trail_fib_use = b.trail_fib_use, r.trail_dual = b.trail_dual,
--          r.max_hold_bars = b.max_hold_bars, r.max_hold_bars_hard = b.max_hold_bars_hard, r.time_stop_extend = b.time_stop_extend,
--          r.buy_order = b.buy_order;
--   DELETE FROM stock.master_codes WHERE `system`='stock' AND source='setting' AND category='batch'
--      AND code IN ('WAVE2_MIN_VOL_PCT', 'WAVE2_MIN_BREADTH');
-- ============================================================================

-- ① 백업(지금 설정 전체)
CREATE TABLE IF NOT EXISTS stock.user_option_reco_bak_20261116 AS
SELECT * FROM stock.user_option_reco WHERE user_id IN (1, 2, 3, 4, 6);

-- ② 매도 설정 통일
UPDATE stock.user_option_reco
   SET stop_loss_pct      = 0.0800,
       take_profit_pct    = 0.3000,
       use_trailing       = 1,
       trail_activate_pct = 0.0800,
       k_trail_atr        = 2.50,
       trail_drawdown_pct = NULL,
       trail_giveback_pct = NULL,
       trail_fib_use      = 0,
       trail_dual         = 0,
       max_hold_bars      = 7,
       max_hold_bars_hard = 7,
       time_stop_extend   = 0,
       buy_order          = 'composite_rank_no:asc'
 WHERE user_id IN (1, 2, 3, 4, 6);

-- ③ 매수 게이트 기준값
INSERT INTO stock.master_codes (`system`, source, category, code, `desc`) VALUES
    ('stock', 'setting', 'batch', 'WAVE2_MIN_VOL_PCT', '0.6667'),
    ('stock', 'setting', 'batch', 'WAVE2_MIN_BREADTH', '0.40')
ON DUPLICATE KEY UPDATE `desc` = VALUES(`desc`);

-- 참고: master_codes 의 WAVE2_MIN_SHAPE_PCT(0.6)·PREFILTER_MIN_AMT20 은 claude/remove-mode-numbering 브랜치 코드가 읽는 값이다.
--       운영 배치는 main 계열(2026-11-16 사용자 확인)이라 지금은 아무 코드도 읽지 않는다. 나중에 그 브랜치를 합치면
--       종합순위에 shape 하한이 겹쳐 걸리므로, 그때 아래 줄로 끈다.
-- UPDATE stock.master_codes SET `desc` = '0' WHERE `system`='stock' AND source='setting' AND category='batch' AND code='WAVE2_MIN_SHAPE_PCT';
