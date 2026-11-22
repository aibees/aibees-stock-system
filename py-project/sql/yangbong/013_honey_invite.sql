-- ============================================================================
-- yangbong/013_honey_invite.sql  (2026-11-22)
--
-- 꿀 2단계: 친구 초대. 기획: yangbong-store-vue/docs/points-plan.md
--   초대받은 친구가 가입 후 내 코드를 넣고, 그 뒤 3일(서로 다른 날) 출석하면 나 +300 · 친구 +100.
--   한 사람은 한 번만 코드를 넣는다. 가입한 지 14일이 지난 계정은 넣을 수 없다. 같은 기기에서는 한 번만.
--   초대한 사람은 한 달에 10명까지 꿀을 받는다(그 뒤로는 초대는 되지만 꿀은 없다).
--
--   honey_invite_code : 사람마다 초대 코드 1개(처음 초대 화면을 열 때 만든다).
--   honey_invite      : 코드를 넣은 기록. invitee 1명당 1행. completed_at 이 있으면 보상 완료.
--     device_id : 화면이 만든 기기 표시(앱 저장소의 무작위 값). 같은 기기 반복 가입으로 꿀을 찍어 내는 것을 막는다.
--   탈퇴하면 본인 행을 지운다(router_account._ACCOUNT_DELETE_TABLES). 남이 나를 초대한 기록(inviter_id)은
--   상대의 기록이라 남지만 개인 식별 정보는 없다.
--
-- 적용 순서: 012_honey.sql 다음, 이 SQL → 양봉상회 API 배포 → 화면 배포. 여러 번 실행해도 된다.
-- ============================================================================

CREATE TABLE IF NOT EXISTS yangbong.honey_invite_code (
    user_id     INT          NOT NULL,
    code        VARCHAR(12)  NOT NULL,
    created_at  DATETIME     NOT NULL,
    PRIMARY KEY (user_id),
    UNIQUE KEY uq_invite_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='꿀 친구 초대 코드. 탈퇴 시 삭제';

CREATE TABLE IF NOT EXISTS yangbong.honey_invite (
    invitee_id    INT          NOT NULL COMMENT '코드를 넣은 사람(user_id 열 이름이 아니라 탈퇴 삭제는 별도 처리)',
    user_id       INT          NOT NULL COMMENT '= invitee_id. 탈퇴 일괄 삭제(user_id 열 기준)용',
    inviter_id    INT          NOT NULL,
    code          VARCHAR(12)  NOT NULL,
    device_id     VARCHAR(64)  NULL,
    redeemed_at   DATETIME     NOT NULL,
    completed_at  DATETIME     NULL,
    PRIMARY KEY (invitee_id),
    KEY idx_invite_inviter (inviter_id, completed_at),
    KEY idx_invite_device (device_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='꿀 친구 초대 기록. 탈퇴 시 본인 행 삭제';

GRANT SELECT, INSERT, UPDATE, DELETE ON yangbong.honey_invite_code TO 'yangbong'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON yangbong.honey_invite TO 'yangbong'@'%';
