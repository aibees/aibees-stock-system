// 공지사항 공통 — 목록(NoticeList)·상세(NoticeDetail)·홈(Home) 이 같이 쓴다.
//   API : GET /api/v1/notices?page=&size=  /  GET /api/v1/notices/<id>  (py-naver-stock-theme router_notice.py)
//   카테고리는 뱃지 없이 글자색으로만 구분한다. 목록에 없는 카테고리는 기본 글자색.
// 본문 HTML sanitize(DOMPurify)는 상세 화면만 쓰므로 noticeHtml.js 로 분리했다 — 홈·라우터가 이 파일을 읽어도 DOMPurify 가 메인 번들에 안 실린다.

export const NOTICE_LIST_PATH = '/board/notice';
// 짧은 주소 /notice/<notice_id> 는 router.js 가 여기(?id=)로 리다이렉트한다.
export const NOTICE_DETAIL_PATH = '/board/notice/detail';

const CATEGORY_CLASS = {
    '공지': 'cat-notice',
    '점검': 'cat-maint',
    '업데이트': 'cat-update',
    '이벤트': 'cat-event',
};

export const noticeCategoryClass = (category) => CATEGORY_CLASS[category] ?? 'cat-etc';

// 서버 created_date('2026-10-25T09:00:00' 또는 '2026-10-25 09:00:00') → '2026.10.25'
export const noticeDateText = (value) => {
    const s = String(value ?? '');
    return s.length >= 10 ? s.slice(0, 10).replaceAll('-', '.') : s;
};
