-- ============================================================================
-- stock/004_inverse_etf_buy_target.sql  (2026-11-17)
--
-- 매수타겟 배치(StockBuyCheckJob)에 주식 인버스 ETF 를 더하는 설정. master_codes stock/setting/batch (배치가 매 실행마다 읽음).
--   INVERSE_ETF          = 'Y'  : 켬(기본). 'N' 이면 예전처럼 원래 목록만 돈다.
--   INVERSE_ETF_EXCLUDE  = 쉼표 구분 낱말 — ETF 이름에 들어가면 뺀다(달러·채권·원자재 인버스 제외용).
--   → 이 행이 없어도 코드 기본값이 같아서 동작은 같다. 화면·운영에서 끄거나 낱말을 바꾸려면 이 행을 고친다.
--
-- 동작 요약(사용자 결정: 주식 인버스 전체, ETF 만, 실전(워커)까지)
--   · 이름에 '인버스'가 들어간 거래 중 ETF(group_code='EF') 중 위 낱말이 없는 것 = 2026-11-17 기준 21종목 추가
--     (KODEX·TIGER·ACE 인버스 3종목은 원래 배치 목록에 있던 종목이라 예전과 똑같이 다룬다)
--   · 다른 종목과 같은 판정 — 2파 신호가 나면 종합순위에 들어가 워커가 살 수 있다.
--   · 실전 게이트 모집단(시장 폭·변동성 백분위)과 shape 학습셋에는 넣지 않는다(게이트 기준은 지금 그대로).
--
-- 적용 순서: ① 이 SQL(선택, 기본값과 같음) → ② 배치 배포(StockBuyCheckJob) — 워커는 재시작 불필요(매수타겟 테이블을 읽음)
-- 확인:
--   SELECT code, `desc` FROM stock.master_codes WHERE `system`='stock' AND source='setting' AND category='batch'
--      AND code LIKE 'INVERSE_ETF%';
--   배치 로그: "[인버스 ETF] N종목 추가(…)" 줄
-- 끄기:
--   UPDATE stock.master_codes SET `desc` = 'N' WHERE `system`='stock' AND source='setting' AND category='batch' AND code='INVERSE_ETF';
-- 되돌리기:
--   DELETE FROM stock.master_codes WHERE `system`='stock' AND source='setting' AND category='batch'
--      AND code IN ('INVERSE_ETF', 'INVERSE_ETF_EXCLUDE');   -- 행이 없으면 코드 기본값(켬)이므로, 완전히 끄려면 위 '끄기'를 쓴다
-- ============================================================================

INSERT INTO stock.master_codes (`system`, source, category, code, `desc`) VALUES
    ('stock', 'setting', 'batch', 'INVERSE_ETF', 'Y'),
    ('stock', 'setting', 'batch', 'INVERSE_ETF_EXCLUDE',
     '달러,엔선물,유로,위안,국채,국고채,채권,금리,원유,WTI,골드,금선물,은선물,팔라듐,구리,천연가스,농산물')
ON DUPLICATE KEY UPDATE `desc` = VALUES(`desc`);
