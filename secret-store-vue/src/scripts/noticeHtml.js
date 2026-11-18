// 공지 본문 HTML — 상세(NoticeDetail)에서만 쓴다. notice.js 에서 분리(메인 번들에서 DOMPurify 제외).
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
