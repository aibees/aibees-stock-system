-- ============================================================================
-- yangbong/014_daily_issue.sql  (2026-11-22)
--
-- 오늘의 경제 이슈: 하루 1건. 홈 카드 + 상세 화면(/issue). 상세 안에 '오늘 강했던 업종 TOP 3'.
--   AI 워커(ai_job_worker)가 매일 06:30(KST)에 만든다.
--   공통코드 stock/setting/daily_issue 의 PUBLISH_MODE 로 공개 방식을 고른다.
--     REVIEW(기본·값이 없을 때도) : 초안(DRAFT)을 만들고 REVIEW_EMAIL 로 검토 메일을 보낸다. 메일의 [확인]=공개, [보류]=보류.
--     AUTO                       : 만들자마자 공개(PUBLISHED). 메일을 보내지 않는다.
--
--   status   : DRAFT(검토 전) · PUBLISHED(공개) · HELD(보류) · FAILED(만들기 실패, error 참고. 10분 뒤 다시, 하루 3번까지)
--   why_text : '왜 중요할까요' 항목. 줄바꿈으로 나눈다.
--   sources  : JSON [{title, press, url}] — 원문 기사 링크. 기사 문장은 옮기지 않는다.
--   sectors  : JSON [{market, sector_cd, sector_name, chg_rate, leaders[], why}] — 만들 때의 업종 TOP 3(sector_ymd 종가 기준)
--
-- 적용 순서: 이 SQL → 양봉상회 API·AI 워커 배포(.env.yangbong 에 SMTP_* 추가) → 화면 배포. 여러 번 실행해도 된다.
-- ============================================================================

CREATE TABLE IF NOT EXISTS yangbong.daily_issue (
    ymd           CHAR(8)       NOT NULL COMMENT '이슈 날짜(KST)',
    status        VARCHAR(10)   NOT NULL DEFAULT 'DRAFT',
    title         VARCHAR(200)  NOT NULL DEFAULT '',
    keywords      VARCHAR(200)  NOT NULL DEFAULT '' COMMENT '쉼표로 구분, # 없이',
    what_text     TEXT          NULL COMMENT '무슨 일이 있었나요',
    why_text      TEXT          NULL COMMENT '왜 중요할까요(줄바꿈 구분)',
    term_name     VARCHAR(60)   NULL COMMENT '알아두면 좋은 말',
    term_desc     VARCHAR(400)  NULL,
    sources       TEXT          NULL COMMENT 'JSON 원문 기사',
    sector_ymd    CHAR(8)       NULL COMMENT '업종 등락 기준일',
    sectors       TEXT          NULL COMMENT 'JSON 업종 TOP 3',
    model         VARCHAR(60)   NULL,
    attempts      INT           NOT NULL DEFAULT 0,
    error         VARCHAR(500)  NULL,
    mailed_at     DATETIME      NULL COMMENT '검토 메일 보낸 시각',
    created_at    DATETIME      NOT NULL,
    updated_at    DATETIME      NOT NULL,
    published_at  DATETIME      NULL,
    PRIMARY KEY (ymd),
    KEY idx_daily_issue_status (status, ymd)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='오늘의 경제 이슈';

GRANT SELECT, INSERT, UPDATE, DELETE ON yangbong.daily_issue TO 'yangbong'@'%';

-- 공개 방식(공통코드). REVIEW → AUTO 로 바꾸면 다음 날부터 메일 없이 바로 공개된다.
INSERT IGNORE INTO yangbong.master_codes (`system`, source, category, code, `desc`)
VALUES ('stock', 'setting', 'daily_issue', 'PUBLISH_MODE', 'REVIEW'),
       ('stock', 'setting', 'daily_issue', 'REVIEW_EMAIL', 'chagoklabs@gmail.com');

-- 확인
-- SELECT ymd, status, title, mailed_at, published_at FROM yangbong.daily_issue ORDER BY ymd DESC LIMIT 7;
-- 바로 게시로 바꾸기:  UPDATE yangbong.master_codes SET `desc` = 'AUTO'
--                      WHERE `system` = 'stock' AND source = 'setting' AND category = 'daily_issue' AND code = 'PUBLISH_MODE';
