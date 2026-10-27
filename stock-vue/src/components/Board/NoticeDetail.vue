<template>
    <div id="notice-detail">
        <BrandHeader :title="title" :back="backPath" />

        <div class="contents">
            <article v-if="notice" class="notice">
                <h2 class="title">{{ notice.title }}</h2>
                <div class="meta">
                    <span :class="['cat', noticeCategoryClass(notice.category)]">{{ notice.category }}</span>
                    <span class="date">{{ noticeDateText(notice.created_date) }}</span>
                </div>
                <!-- 본문: HTML 이면 sanitize 후 v-html, 태그가 없으면 일반 텍스트(줄바꿈 그대로) -->
                <div v-if="bodyHtml !== null" class="body is-html" v-html="bodyHtml"></div>
                <div v-else class="body">{{ notice.content }}</div>
            </article>

            <p v-else-if="!isLoading" class="empty-box">{{ errorMsg }}</p>

            <button type="button" class="list-btn" @click="router.push(NOTICE_LIST_PATH)">목록으로</button>
        </div>
    </div>
</template>

<script setup>
/**
 * 공지사항 상세(읽기 전용). 메뉴 목록엔 숨김(display_flag='N'), 목록·홈에서 ?id= 로 들어온다.
 *   GET /api/v1/notices/<id>
 *   홈에서 들어오면(?from=home) ‹ 버튼이 홈으로 돌아간다.
 *   짧은 주소 /notice/<notice_id> 로도 들어온다(router.js 리다이렉트).
 */
import aibeesApi from '@scripts/aibeesApi.js';
import { NOTICE_LIST_PATH, noticeCategoryClass, noticeDateText, isNoticeHtml, sanitizeNoticeHtml } from '@scripts/notice.js';

const route = useRoute();
const router = useRouter();
const title = ref('공지사항');
const notice = ref(null);
const isLoading = ref(false);
const errorMsg = ref('');

// v-html 로 그리는 값은 반드시 이 computed 를 거친다(sanitize).
const bodyHtml = computed(() => {
    const content = notice.value?.content;
    return isNoticeHtml(content) ? sanitizeNoticeHtml(content) : null;
});

const backPath = computed(() => (route.query.from === 'home' ? '/home' : NOTICE_LIST_PATH));

const load = async (id) => {
    notice.value = null;
    errorMsg.value = '';
    if (!/^\d+$/.test(String(id ?? ''))) {
        errorMsg.value = '공지사항을 찾을 수 없습니다.';
        return;
    }
    isLoading.value = true;
    try {
        const { data } = await aibeesApi.get(`/api/v1/notices/${id}`);
        notice.value = data?.data ?? null;
        if (!notice.value) errorMsg.value = '공지사항을 찾을 수 없습니다.';
    } catch (e) {
        errorMsg.value = e?.response?.status === 404 ? '공지사항을 찾을 수 없습니다.' : '공지사항을 불러오지 못했습니다.';
    } finally {
        isLoading.value = false;
    }
};

watch(() => route.query.id, (id) => load(id), { immediate: true });
</script>

<style scoped lang="scss">
// 양봉상회 디자인 토큰
$card:  #FFFFFF;
$line:  #EFE2BC;
$brown: #7A4423;
$ink:   #2B1D14;
$sub:   #6B5B4E;
$sub-2: #7A6B5D;
$up:    #C8282A;
$down:  #1F5BD1;
$amber: #A0662F;

#notice-detail {
    min-height: 100vh;
    background: $card;
    color: $ink;
    text-align: left;
    font-family: 'Pretendard', 'IBM Plex Sans KR', -apple-system, 'Apple SD Gothic Neo', sans-serif;
}

.contents {
    max-width: 720px;
    margin: 0 auto;
    padding: 16px 16px 24px;
}

.notice {
    .title { margin: 0; font-size: 19px; font-weight: 700; line-height: 1.4; word-break: keep-all; }
    // 카테고리·날짜는 오른쪽
    .meta {
        display: flex;
        justify-content: flex-end;
        gap: 8px;
        margin-top: 6px;
        padding-bottom: 14px;
        border-bottom: 1px solid $line;
        font-size: 12px;
        color: $sub;
    }
    .date { font-variant-numeric: tabular-nums; }
    .body {
        padding: 16px 0 20px;
        border-bottom: 1px solid $line;
        font-size: 15px;
        line-height: 1.7;
        white-space: pre-wrap;
        word-break: break-word;
    }
    // HTML 본문: 줄바꿈은 태그로만. v-html 내용은 scoped 밖이라 :deep 으로 꾸민다.
    .body.is-html {
        white-space: normal;
        :deep(h3) { margin: 20px 0 8px; font-size: 16px; font-weight: 700; color: $brown; }
        :deep(h4) { margin: 16px 0 6px; font-size: 15px; font-weight: 700; }
        :deep(h3:first-child), :deep(h4:first-child), :deep(p:first-child) { margin-top: 0; }
        :deep(p) { margin: 0 0 10px; }
        :deep(strong), :deep(b) { font-weight: 700; }
        :deep(ul), :deep(ol) { margin: 0 0 10px; padding-left: 20px; }
        :deep(li) { margin: 2px 0; }
        :deep(blockquote) { margin: 0 0 10px; padding-left: 12px; border-left: 3px solid $line; color: $sub; }
        :deep(hr) { border: 0; border-top: 1px solid $line; margin: 16px 0; }
        :deep(a) { color: $down; text-decoration: underline; }
    }
}

// 카테고리: 글자색만 (NoticeList 와 같음)
.cat { font-weight: 600; }
.cat-notice { color: $brown; }
.cat-maint  { color: $up; }
.cat-update { color: $down; }
.cat-event  { color: $amber; }
.cat-etc    { color: $sub-2; }

.empty-box { text-align: center; padding: 56px 0; color: $sub; font-size: 14px; }

.list-btn {
    display: block;
    margin: 12px auto 0;
    padding: 10px 16px;
    border: 0;
    background: transparent;
    color: $brown;
    font: inherit;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
}
</style>
