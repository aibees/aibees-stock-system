-- ============================================================================
-- 기본 단계(BASIC, 옛 기계식 알고리즘) 추천 종목 테이블 + 공통코드 등록
--
--   trade_buy_target_stock  (기존, 변경 없음) : 2파 돌파 종합순위. 워커·성과·시뮬이 읽는다.
--   trade_buy_target_basic  (신규)            : 옛 기계식 알고리즘(watch 게이트)이 고른 종목. 기본 단계 목록용.
--
-- 기존 테이블의 키·컬럼·데이터를 건드리지 않는다 → 매매 경로(워커)에 영향이 없다.
-- 예전에 기존 테이블에 저장돼 있던 옛 알고리즘 행(rank_no 가 있는 과거 행)은 그대로 두고,
-- 서버가 그 행을 기본 단계 종목으로도 인정한다(과거 날짜 조회 유지). 이전(migration) 작업은 없다.
--
-- ※ 실행 순서: 이 SQL → 코드 배포. (새 코드가 trade_buy_target_basic 에 쓰고 읽는다.)
-- ============================================================================

CREATE TABLE IF NOT EXISTS trade_buy_target_basic (
    ymd                VARCHAR(8)     NOT NULL,
    stock_code         VARCHAR(45)    NOT NULL,
    rank_no            INT            NULL,
    stock_name         VARCHAR(45)    NULL,
    `open`             DECIMAL(18,8)  NULL,
    high               DECIMAL(18,8)  NULL,
    low                DECIMAL(18,8)  NULL,
    `close`            DECIMAL(18,8)  NULL,
    volume             DECIMAL(18,8)  NULL,
    rate               VARCHAR(45)    NULL,
    action_type        VARCHAR(45)    NULL,
    macd_cross         VARCHAR(45)    NULL,
    obv_cross          VARCHAR(45)    NULL,
    is_vol_limit       VARCHAR(45)    NULL,
    is_under_bb_upper  VARCHAR(45)    NULL,
    is_over_on_mid     VARCHAR(45)    NULL,
    is_vol_surge       VARCHAR(45)    NULL,
    is_bb_mid_breakout VARCHAR(45)    NULL,
    eps                VARCHAR(45)    NULL,
    pbr                VARCHAR(45)    NULL,
    per                VARCHAR(45)    NULL,
    roe                VARCHAR(45)    NULL,
    peg                VARCHAR(45)    NULL,
    score              DECIMAL(6,2)   NULL,
    shape_proba        DECIMAL(6,4)   NULL,
    shape_exhaustion   VARCHAR(1)     NULL,
    PRIMARY KEY (ymd, stock_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='기본 단계 추천(옛 기계식 알고리즘). 워커는 읽지 않는다';

-- 공통코드: 알고리즘 → 열람 단계 번호(desc). 서버(RecoLevel)가 읽는다. 행이 없으면 아래와 같은 기본값을 쓴다.
--   BASIC=옛 기계식(trade_buy_target_basic) / PREMIUM=2파 종합순위(trade_buy_target_stock) / PRIVATE=30분봉 재검증(연구 중)
INSERT INTO master_codes (`system`, source, category, code, `desc`) VALUES
    ('stock', 'setting', 'reco_algo', 'BASIC',   '1'),
    ('stock', 'setting', 'reco_algo', 'PREMIUM', '2'),
    ('stock', 'setting', 'reco_algo', 'PRIVATE', '3')
ON DUPLICATE KEY UPDATE `desc` = VALUES(`desc`);

-- 옛 공통코드 정리(BASE_RECO 는 폐기: 기본 추천은 항상 저장한다)
DELETE FROM master_codes
 WHERE `system` = 'stock' AND source = 'setting' AND category = 'batch' AND code = 'BASE_RECO';

-- ============================================================================
-- 확인 쿼리
--   SELECT ymd, COUNT(*) FROM trade_buy_target_basic GROUP BY ymd ORDER BY ymd DESC LIMIT 5;   -- 첫 배치 이후
--   SELECT code, `desc` FROM master_codes WHERE category = 'reco_algo';
--
-- ROLLBACK
--   DROP TABLE trade_buy_target_basic;
--   DELETE FROM master_codes WHERE `system`='stock' AND source='setting' AND category='reco_algo';
-- ============================================================================
