-- ============================================================================
-- yangbong/015_daily_issue_reject.sql  (2026-11-22)
--
-- 오늘의 경제 이슈 검토 메일 버튼을 [승인]/[반려]로. 반려하면 1분 안에 새 초안을 만들어 메일을 다시 보낸다.
--   feedback : 그날 반려된 초안 제목과 반려 이유(선택) 기록. 다음 초안을 만들 때 AI 에 함께 준다(같은 글을 다시 쓰지 않게).
--   status 에 REJECTED(반려 — 새 글 만들기 대기)가 생긴다.
--   하루에 만드는 횟수는 실패·반려를 합쳐 5번까지(daily_issue_service.MAX_ATTEMPTS).
--
-- 적용 순서: 014 다음, 이 SQL → 양봉상회 API·AI 워커 배포(서버를 먼저 배포하면 'Unknown column feedback' 오류).
-- 한 번만 실행한다(다시 실행하면 'Duplicate column' 오류 — 이미 적용된 것이니 무시해도 된다).
-- ============================================================================

ALTER TABLE yangbong.daily_issue
    ADD COLUMN feedback TEXT NULL COMMENT '반려된 초안 제목·이유(다음 초안에 반영)' AFTER error;
