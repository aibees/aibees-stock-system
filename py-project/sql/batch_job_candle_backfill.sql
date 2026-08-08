-- ============================================================
-- 매수추천 종목 차트 백필 배치 등록
--
--   최근 60일 안에 매수추천(trade_buy_target_stock)에 한 번이라도 등장한 종목의
--   일봉 + 지표를 trade_candle_data 에 UPSERT 한다. (화면/백테스트 테스트용)
--
--   실행: 매일 21:00 KST · 평일
--     · 매수추천 배치(STOCK_BUY_CHECK_JOB)가 20:00 이므로
--       그날 새로 추천된 종목까지 포함된다.
--     · PK(coin, datetime) UPSERT 라 매일 돌려도 중복이 쌓이지 않는다.
--
--   ※ APScheduler CronTrigger 는 timezone=Asia/Seoul 로 등록된다
--     (scheduler_app/runner.py 의 load_jobs 참조).
-- ============================================================

INSERT INTO batch_job_master
    (job_id, job_name, module_name, class_name,
     cron_minute, cron_hour, cron_day_of_week, enabled_flag)
VALUES
    ('STOCK_CANDLE_BACKFILL_JOB',
     '매수추천 종목 차트 백필',
     'app.batches.jobs.TradeCandleBackfillJob',
     'TradeCandleBackfillJob',
     '0', '21', 'mon-fri', 'Y');


-- ============================================================
-- 확인
-- ============================================================
-- SELECT job_id, job_name, cron_hour, cron_minute, cron_day_of_week, enabled_flag
--   FROM batch_job_master ORDER BY cron_hour;
--
-- ※ 등록 후 스케줄러에 반영하려면 둘 중 하나:
--     GET  /api/v1/jobs/reload        (재시작 없이 job 목록 재적재)
--     또는 py-stock-batch 컨테이너 재시작

-- ============================================================
-- 수동 실행 (즉시 1회)
-- ============================================================
-- curl -X POST http://<host>:5557/api/v1/jobs/once/STOCK_CANDLE_BACKFILL_JOB \
--      -H 'Content-Type: application/json' -d '{}'
--
-- 파라미터 예시:
--   {"days": 90}                  최근 90일 추천 종목으로 확대
--   {"end_date": "2026-08-07"}    기준일 지정(과거 시점 재현)
--   {"stock_codes": ["035420"]}   특정 종목만 (대상 조회 건너뜀 · 테스트용)

-- ============================================================
-- 적재 결과 확인
-- ============================================================
-- SELECT COUNT(DISTINCT coin) AS codes, COUNT(*) AS rows_total,
--        MIN(datetime) AS min_dt, MAX(datetime) AS max_dt
--   FROM trade_candle_data;
--
-- 최근 60일 추천 종목 중 아직 캔들이 없는 종목:
-- SELECT DISTINCT t.stock_code, t.stock_name
--   FROM trade_buy_target_stock t
--   LEFT JOIN trade_candle_data c ON c.coin = t.stock_code
--  WHERE t.ymd >= DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL 60 DAY), '%Y%m%d')
--    AND c.coin IS NULL;
