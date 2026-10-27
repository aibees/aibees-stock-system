<template>
    <div id="notice-list">
        <BrandHeader :title="title" back="/menu" />

        <div class="contents">
            <div class="list-head">
                <h2>공지사항 <span v-if="total" class="count">{{ total }}</span></h2>
            </div>

            <ul v-if="items.length" class="notice-list">
                <li v-for="n in items" :key="n.notice_id">
                    <button type="button" class="notice-row" @click="goDetail(n)">
                        <span class="title">{{ n.title }}</span>
                        <span class="meta">
                            <span :class="['cat', noticeCategoryClass(n.category)]">{{ n.category }}</span>
                            <span class="date">{{ noticeDateText(n.created_date) }}</span>
                        </span>
                    </button>
                </li>
            </ul>

            <p v-else-if="!isLoading" class="empty-box">{{ errorMsg || '등록된 공지사항이 없습니다.' }}</p>

            <button v-if="hasMore" type="button" class="more-btn" :disabled="isLoading" @click="loadPage(page + 1)">
                {{ isLoading ? '불러오는 중…' : '더 보기' }}
            </button>
        </div>
    </div>
</template>

<script setup>
/**
 * 공지사항 목록(읽기 전용). 작성일자 최신순, 20건씩 '더 보기'.
 *   GET /api/v1/notices?page=&size=  → 누르면 상세(/board/notice/detail?id=)
 */
import aibeesApi from '@scripts/aibeesApi.js';
import { NOTICE_DETAIL_PATH, noticeCategoryClass, noticeDateText } from '@scripts/notice.js';

const PAGE_SIZE = 20;

const router = useRouter();
const title = ref('공지사항');
const items = ref([]);
const page = ref(0);
const total = ref(0);
const totalPages = ref(0);
const isLoading = ref(false);
const errorMsg = ref('');

const hasMore = computed(() => page.value + 1 < totalPages.value);

const loadPage = async (p) => {
    isLoading.value = true;
    errorMsg.value = '';
    try {
        const { data } = await aibeesApi.get('/api/v1/notices', { params: { page: p, size: PAGE_SIZE } });
        items.value = p === 0 ? (data?.data ?? []) : [...items.value, ...(data?.data ?? [])];
        page.value = p;
        total.value = data?.totalElements ?? 0;
        totalPages.value = data?.totalPages ?? 0;
    } catch (e) {
        errorMsg.value = '공지사항을 불러오지 못했습니다.';
    } finally {
        isLoading.value = false;
    }
};

const goDetail = (n) => router.push({ path: NOTICE_DETAIL_PATH, query: { id: n.notice_id } });

onMounted(() => loadPage(0));
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

#notice-list {
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

.list-head {
    margin-bottom: 4px;
    h2 { margin: 0; font-size: 18px; font-weight: 700; }
    .count { color: $amber; }
}

.notice-list { margin: 0; padding: 0; list-style: none; border-top: 1px solid $line; }
.notice-row {
    width: 100%;
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 12px;
    padding: 12px 0;
    border: 0;
    border-bottom: 1px solid $line;
    background: transparent;
    color: $ink;
    text-align: left;
    font: inherit;
    cursor: pointer;

    .title { flex: 1; min-width: 0; font-size: 15px; font-weight: 600; line-height: 1.4; word-break: keep-all; }
    // 카테고리·날짜는 오른쪽
    .meta { flex-shrink: 0; display: flex; gap: 8px; font-size: 12px; color: $sub; white-space: nowrap; }
    .date { font-variant-numeric: tabular-nums; }
}

// 카테고리: 글자색만
.cat { font-weight: 600; }
.cat-notice { color: $brown; }
.cat-maint  { color: $up; }
.cat-update { color: $down; }
.cat-event  { color: $amber; }
.cat-etc    { color: $sub-2; }

.empty-box { text-align: center; padding: 56px 0; color: $sub; font-size: 14px; }

.more-btn {
    display: block;
    width: 100%;
    margin-top: 12px;
    padding: 12px 0;
    border: 0;
    background: transparent;
    color: $brown;
    font: inherit;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    &:disabled { color: $sub-2; cursor: default; }
}
</style>
