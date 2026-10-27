// 공지사항 공통 — 목록(NoticeList)·상세(NoticeDetail)·홈(Home) 이 같이 쓴다.
//   API : GET /api/v1/notices?page=&size=  /  GET /api/v1/notices/<id>  (py-naver-stock-theme router_notice.py)
//   카테고리는 뱃지 없이 글자색으로만 구분한다. 목록에 없는 카테고리는 기본 글자색.
import DOMPurify from 'dompurify';

// ── 본문 HTML ──
//   notice.content 는 DB 에 직접 넣는 값이라 화면에 그리기 직전에 항상 sanitize 한다(v-html 단일 진입점).
//   허용: 소제목(h3·h4)·강조(strong/b·em/i·u·s)·문단(p·br·hr·blockquote)·목록(ul·ol·li)·링크(a href).
//   style·class·이미지·표·script·이벤트 속성은 전부 제거. 링크는 http(s)/mailto 만, 새 창으로 연다.
const ALLOWED_TAGS = ['h3', 'h4', 'p', 'br', 'hr', 'blockquote', 'strong', 'b', 'em', 'i', 'u', 's',
    'ul', 'ol', 'li', 'a'];
const ALLOWED_ATTR = ['href'];
const ALLOWED_URI_REGEXP = /^(?:https?:|mailto:)/i;

DOMPurify.addHook('afterSanitizeAttributes', (node) => {
    if (node.tagName === 'A' && node.hasAttribute('href')) {
        node.setAttribute('target', '_blank');
        node.setAttribute('rel', 'noopener noreferrer');
    }
});

// 태그가 하나도 없으면 예전처럼 일반 텍스트(줄바꿈 그대로)로 본다.
export const isNoticeHtml = (content) => /<\/?[a-z][a-z0-9]*[\s>/]/i.test(String(content ?? ''));

export const sanitizeNoticeHtml = (content) => DOMPurify.sanitize(String(content ?? ''), {
    ALLOWED_TAGS,
    ALLOWED_ATTR,
    ALLOWED_URI_REGEXP,
});

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
