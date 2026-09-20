<template>
    <div id="stock-analysis">
        <Headers :prop_title="title" />

        <div class="contents">
            <!-- 검색 섹션 -->
            <section class="search-section">
                <SAutoInput
                id="search-input"
                v-model:name="inputName"
                v-model:code="inputCode"
                @search="stockSearchHandler"
                width="100%" />
                <button v-if="inputCode" class="chart-btn" @click="goToChart">차트보기</button>
            </section>

            <transition name="fade-slide">
                <div v-if="stockDetail" class="body-box">

                    <!-- ① 기업개요 + 재무현황 (버튼 갱신, 실적발표월만) -->
                    <section class="ai-result-section">
                        <div class="section-header">
                            <span class="section-icon">🏢</span>
                            <span class="section-title">기업개요 · 재무현황</span>
                            <span v-if="overview" class="token-info">{{ formatUpdatedAt(overview.updated_at) }} 업데이트</span>
                            <button type="button" class="ai-refresh-btn" :disabled="overviewButtonDisabled" @click="refreshOverview">
                                {{ overviewButtonLabel }}
                            </button>
                        </div>
                        <div class="ai-result-body compact">
                            <div v-if="overviewHtml" class="markdown-body" v-html="overviewHtml" />
                            <div v-else-if="overviewLoading || overviewRefreshing" class="ai-loading">
                                <div class="loading-dots"><span></span><span></span><span></span></div>
                                <span class="loading-label">불러오는 중입니다…</span>
                            </div>
                            <div v-else class="ai-empty">아직 생성된 내용이 없습니다. 새로고침을 눌러주세요.</div>
                        </div>
                    </section>

                    <!-- ② 현재 테마 (버튼 갱신, 주 1회 권장) -->
                    <section class="ai-result-section">
                        <div class="section-header">
                            <span class="section-icon">🔥</span>
                            <span class="section-title">현재 테마</span>
                            <span v-if="theme" class="token-info">{{ formatUpdatedAt(theme.updated_at) }} 업데이트</span>
                            <button type="button" class="ai-refresh-btn" :disabled="themeButtonDisabled" @click="refreshTheme">
                                {{ themeButtonLabel }}
                            </button>
                        </div>
                        <div class="ai-result-body compact">
                            <div v-if="themeHtml" class="markdown-body" v-html="themeHtml" />
                            <div v-else-if="themeLoading || themeRefreshing" class="ai-loading">
                                <div class="loading-dots"><span></span><span></span><span></span></div>
                                <span class="loading-label">불러오는 중입니다…</span>
                            </div>
                            <div v-else class="ai-empty">아직 생성된 내용이 없습니다. 새로고침을 눌러주세요.</div>
                        </div>
                    </section>

                    <!-- ③ 최근 공시·뉴스 (자동, 2시간 캐시) -->
                    <section class="ai-result-section">
                        <div class="section-header">
                            <span class="section-icon">📰</span>
                            <span class="section-title">최근 공시 · 뉴스</span>
                            <span v-if="news" class="token-info">{{ formatUpdatedAt(news.updated_at) }} 업데이트</span>
                        </div>
                        <div class="ai-result-body compact">
                            <div v-if="newsHtml" class="markdown-body" v-html="newsHtml" />
                            <div v-else-if="newsLoading" class="ai-loading">
                                <div class="loading-dots"><span></span><span></span><span></span></div>
                                <span class="loading-label">뉴스 확인 중입니다…</span>
                            </div>
                            <div v-else class="ai-empty">확인된 뉴스가 없습니다.</div>
                        </div>
                    </section>

                    <!-- ② 최근 분기 실적 -->
                    <!-- <section class="quarterly-section">
                        <div class="section-header">
                            <span class="section-title">최근 분기 실적</span>
                            <span class="section-unit">단위: 억원</span>
                        </div>
                        <div class="quarterly-table">
                            <div class="qt-row qt-head">
                                <div class="qt-cell label-col"></div>
                                <div class="qt-cell" v-for="q in quarterlyResults" :key="q.quarter">{{ q.quarter }}</div>
                            </div>
                            <div class="qt-row">
                                <div class="qt-cell label-col">매출액</div>
                                <div class="qt-cell num" v-for="q in quarterlyResults" :key="'rev-' + q.quarter">
                                    {{ q.revenue }}
                                </div>
                            </div>
                            <div class="qt-row">
                                <div class="qt-cell label-col">영업이익</div>
                                <div class="qt-cell num" v-for="q in quarterlyResults" :key="'op-' + q.quarter">
                                    <span :class="profitClass(q.operatingProfit)">{{ q.operatingProfit }}</span>
                                </div>
                            </div>
                            <div class="qt-row last">
                                <div class="qt-cell label-col">당기순이익</div>
                                <div class="qt-cell num" v-for="q in quarterlyResults" :key="'np-' + q.quarter">
                                    <span :class="profitClass(q.netProfit)">{{ q.netProfit }}</span>
                                </div>
                            </div>
                        </div>
                    </section> -->

                    <!-- ③ 추천 성과 추적 (최근 1달 이내 추천된 경우) -->
                    <section class="rec-section" v-if="recommendationData?.rec_record && recommendationData?.now_record && recommendationData?.max_record">
                        <div class="section-header">
                            <span class="section-title">추천 성과 추적</span>
                            <span class="rec-date-badge">추천일 {{ recommendationData.rec_record.ymd }}</span>
                        </div>
                        <div class="rec-grid">
                            <div class="rec-card base-card">
                                <span class="rec-label">추천당시 종가 {{ recommendationData.rec_record.ymd }}</span>
                                <span class="rec-price">{{ formatNumber(recommendationData.rec_record.close) }}<em>원</em></span>
                                <span class="rec-rate-badge neutral">기준가</span>
                            </div>
                            <div class="rec-card">
                                <span class="rec-label">현재 종가 {{ recommendationData.now_record.ymd }}</span>
                                <span class="rec-price">{{ formatNumber(recommendationData.now_record.close) }}<em>원</em></span>
                                <span class="rec-rate-badge" :class="rateClass(recommendationData.now_record.rate)">
                                    {{ formatRate(recommendationData.now_record.rate) }}
                                </span>
                            </div>
                            <div class="rec-card high-card">
                                <span class="rec-label">추천 후 최고가 {{ recommendationData.max_record.ymd }}</span>
                                <span class="rec-price">{{ formatNumber(recommendationData.max_record.close) }}<em>원</em></span>
                                <span class="rec-rate-badge" :class="rateClass(recommendationData.max_record.rate)">
                                    {{ formatRate(recommendationData.max_record.rate) }}
                                </span>
                            </div>
                        </div>
                    </section>

                </div>
            </transition>
        </div>
    </div>
</template>

<script setup>
import { ref, computed } from 'vue';
import { marked } from 'marked';
import aibeesApi from '@scripts/aibeesApi.js';
import { assUserSession } from '@scripts/stores/user-stores';

// marked 옵션
marked.setOptions({ breaks: true, gfm: true });

const route = useRoute();
const router = useRouter();
const title = ref('종목 심층 분석');
const stockDetail = ref(null);
const inputName = ref('');
const inputCode = ref('');

const userSession = assUserSession();
const ADMIN_USER_ID = 1;
const ANNOUNCEMENT_MONTHS = [2, 5, 8, 11];
const MIN_REFRESH_INTERVAL_MS = 60 * 60 * 1000; // 1시간

const isAdmin = computed(() =>
    userSession.isUserSession() && Number(userSession.user.loginInfo.user_id) === ADMIN_USER_ID
);
const isAnnouncementMonth = computed(() => ANNOUNCEMENT_MONTHS.includes(new Date().getMonth() + 1));

/* ── 기업개요 + 재무현황 (버튼 갱신) ── */
const overview = ref(null);          // { content, updated_at, input_tokens, output_tokens, model } | null
const overviewLoading = ref(false);
const overviewRefreshing = ref(false);
const overviewHtml = computed(() => overview.value?.content ? marked.parse(overview.value.content) : '');
const overviewOnCooldown = computed(() => cooldownRemainingMs(overview.value?.updated_at) > 0);
// 한 번도 생성된 적 없는 종목(overview === null)은 발표월 무관 최초 1회 허용 — 백엔드와 동일 규칙
const overviewButtonDisabled = computed(() =>
    overviewRefreshing.value
    || (!!overview.value && !isAnnouncementMonth.value)
    || (overviewOnCooldown.value && !isAdmin.value)
);
const overviewButtonLabel = computed(() => {
    if (overviewRefreshing.value) return '갱신 중…';
    if (overview.value && !isAnnouncementMonth.value) return '실적발표월(2·5·8·11월)만 가능';
    if (overviewOnCooldown.value && !isAdmin.value) return `${cooldownUntilLabel(overview.value.updated_at)} 이후 가능`;
    return '새로고침';
});

/* ── 현재 테마 (버튼 갱신) ── */
const theme = ref(null);
const themeLoading = ref(false);
const themeRefreshing = ref(false);
const themeHtml = computed(() => theme.value?.content ? marked.parse(theme.value.content) : '');
const themeOnCooldown = computed(() => cooldownRemainingMs(theme.value?.updated_at) > 0);
const themeButtonDisabled = computed(() =>
    themeRefreshing.value || (themeOnCooldown.value && !isAdmin.value)
);
const themeButtonLabel = computed(() => {
    if (themeRefreshing.value) return '갱신 중…';
    if (themeOnCooldown.value && !isAdmin.value) return `${cooldownUntilLabel(theme.value.updated_at)} 이후 가능`;
    return '새로고침';
});

/* ── 최근 공시·뉴스 (자동, 버튼 없음) ── */
const news = ref(null);
const newsLoading = ref(false);
const newsHtml = computed(() => news.value?.content ? marked.parse(news.value.content) : '');

const cooldownRemainingMs = (updatedAt) => {
    if (!updatedAt) return 0;
    return new Date(updatedAt).getTime() + MIN_REFRESH_INTERVAL_MS - Date.now();
};
const cooldownUntilLabel = (updatedAt) => {
    const until = new Date(new Date(updatedAt).getTime() + MIN_REFRESH_INTERVAL_MS);
    return `${String(until.getHours()).padStart(2, '0')}:${String(until.getMinutes()).padStart(2, '0')}`;
};
const formatUpdatedAt = (v) => {
    if (!v) return '';
    const d = new Date(v);
    return `${d.getFullYear()}.${String(d.getMonth() + 1).padStart(2, '0')}.${String(d.getDate()).padStart(2, '0')} `
        + `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
};

// 최근 분기 실적 (mock)
const quarterlyResults = ref([
    { quarter: '24Q2', revenue: '2,841', operatingProfit: '312', netProfit: '228' },
    { quarter: '24Q3', revenue: '3,104', operatingProfit: '-45', netProfit: '-38' },
    { quarter: '24Q4', revenue: '3,520', operatingProfit: '487', netProfit: '361' },
    { quarter: '25Q1', revenue: '3,215', operatingProfit: '401', netProfit: '290' },
]);

// 최근 1달 이내 추천 데이터 (mock, null이면 섹션 미노출)
const recommendationData = ref(null);   // {} 는 truthy 라 v-if 를 통과해 .rec_record.ymd 에서 터졌다

onMounted(() => {
    const code = route.query.stock_code;
    const name = route.query.stock_name;
    if (code) {
        inputCode.value = code;
        inputName.value = name || code;
        stockSearchHandler(code);
    }
});

const goToChart = () => {
    router.push({ path: '/charts/stock', query: { code: inputCode.value } });
};

const stockSearchHandler = (code) => {
    if (!code) return;
    stockDetail.value = { code };
    overview.value = null;
    theme.value = null;
    news.value = null;

    getOverview(code);
    getTheme(code);
    getNews(code);
    getRecommandResult(code);
};

const getOverview = async (code) => {
    overviewLoading.value = true;
    try {
        const { data } = await aibeesApi.get('/api/v1/anthropic/stock-analysis/overview', { params: { stock_code: code } });
        overview.value = data.data;
    } catch (e) {
        console.error(e);
        overview.value = null;
    } finally {
        overviewLoading.value = false;
    }
};

const getTheme = async (code) => {
    themeLoading.value = true;
    try {
        const { data } = await aibeesApi.get('/api/v1/anthropic/stock-analysis/theme', { params: { stock_code: code } });
        theme.value = data.data;
    } catch (e) {
        console.error(e);
        theme.value = null;
    } finally {
        themeLoading.value = false;
    }
};

const getNews = async (code) => {
    newsLoading.value = true;
    try {
        const { data } = await aibeesApi.get('/api/v1/anthropic/stock-analysis/news', { params: { stock_code: code } });
        news.value = data.data;
    } catch (e) {
        console.error(e);
        news.value = null;
    } finally {
        newsLoading.value = false;
    }
};

const refreshOverview = async () => {
    if (!userSession.isUserSession()) {
        alert('로그인 후 이용할 수 있습니다.');
        return;
    }

    let force = false;
    if (overviewOnCooldown.value) {
        if (!isAdmin.value) return;
        if (!confirm('1시간 이내에 이미 갱신되었습니다. 그래도 다시 갱신하시겠습니까?')) return;
        force = true;
    }

    overviewRefreshing.value = true;
    try {
        const { data } = await aibeesApi.post(
            '/api/v1/anthropic/stock-analysis/overview',
            { force },
            { params: { stock_code: inputCode.value } },
        );
        overview.value = data.data;
    } catch (e) {
        console.error(e);
    } finally {
        overviewRefreshing.value = false;
    }
};

const refreshTheme = async () => {
    if (!userSession.isUserSession()) {
        alert('로그인 후 이용할 수 있습니다.');
        return;
    }

    let force = false;
    if (themeOnCooldown.value) {
        if (!isAdmin.value) return;
        if (!confirm('1시간 이내에 이미 갱신되었습니다. 그래도 다시 갱신하시겠습니까?')) return;
        force = true;
    }

    themeRefreshing.value = true;
    try {
        const { data } = await aibeesApi.post(
            '/api/v1/anthropic/stock-analysis/theme',
            { force },
            { params: { stock_code: inputCode.value } },
        );
        theme.value = data.data;
    } catch (e) {
        console.error(e);
    } finally {
        themeRefreshing.value = false;
    }
};

const getRecommandResult = async (code) => {
    try {
        recommendationData.value = null;   // 종목 전환 시 이전 종목 데이터 잔존 방지
        const { data } = await aibeesApi.get(`/api/v1/stocks/rec-record?stock_code=${code}`);
        recommendationData.value = data?.data ?? null;
    } catch (e) {
        recommendationData.value = null;
        console.error(e);
    }
}

const profitClass = (val) => {
    const n = parseFloat(String(val).replace(/,/g, ''));
    if (n > 0) return 'val-up';
    if (n < 0) return 'val-down';
    return '';
};

const rateClass = (rate) => {
    if (rate > 0) return 'rate-up';
    if (rate < 0) return 'rate-down';
    return 'neutral';
};

const formatNumber = (v) => Number(v).toLocaleString();
const formatRate = (v) => (v > 0 ? '+' : '') + v.toFixed(2) + '%';
</script>

<style scoped lang="scss">
/* ── 색상 변수 (Home.vue 동일) ── */
$white:    #ffffff;
$gray-50:  #fafafa;
$gray-100: #efefef;
$gray-200: #dcdcdc;
$gray-300: #c4c4c4;
$gray-400: #9a9a9a;
$gray-500: #737373;
$gray-700: #3d3d3d;
$gray-900: #141414;
$blue:     #141414;
$navy:     #141414;
$red:      #141414;
$amber:    #141414;

/* ── 기본 레이아웃 ── */
#stock-analysis {
    min-height: 100vh;
    background: $white;
    color: $gray-900;
    font-family: 'Pretendard', -apple-system, sans-serif;
}

.contents {
    max-width: 600px;
    margin: 0 auto;
    padding: 20px 16px 100px;
}

/* ── 검색 영역 — SAutoInput 스타일 오버라이드 ── */
.search-section {
    margin-bottom: 20px;
    display: flex;
    flex-direction: column;
    gap: 8px;

    .chart-btn {
        align-self: flex-end;
        padding: 5px 12px;
        border: 1px solid $gray-200;
        border-radius: 0;
        background: $white;
        color: $gray-700;
        font-size: 0.72rem;
        font-weight: 600;
        font-family: inherit;
        cursor: pointer;
        transition: border-color .12s, color .12s, background .12s;

        &:hover { border-color: $blue; color: $blue; background: $gray-50; }
    }

    /* ① 컨테이너 자체 여백 제거 */
    :deep(.auto-complete-container) {
        margin: 0;
        width: 100%;
    }

    /* ② 각 요소별로 :deep() 평탄하게 선언 — 중첩 컴파일 문제 방지 */
    :deep(.search-bar) {
        width: 100% !important;   /* SAutoInput의 width:90% 덮어쓰기 */
        box-sizing: border-box;
        margin: 0 !important;
        background: $white;
        border: 1.5px solid $gray-200;
        border-radius: 0;
        padding: 6px 6px 6px 14px;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
        transition: border-color 0.15s;

        &:focus-within {
            border-color: $blue;
            box-shadow: 0 2px 12px rgba(25, 113, 194, 0.12);
        }
    }

    :deep(.search-bar .search-icon) {
        font-size: 1rem;
        margin-right: 10px;
    }

    :deep(.search-bar input) {
        color: $gray-900;
        font-size: 0.95rem;

        &::placeholder { color: $gray-400; }
    }

    :deep(.search-bar .search-btn) {
        background: $navy;
        color: $white;
        border-radius: 0;
        padding: 9px 18px;
        font-size: 0.88rem;
        font-weight: 700;
        font-family: inherit;
        white-space: nowrap;

        &:hover  { background: $blue; }
        &:active { transform: scale(0.97); }
    }

    /* 자동완성 드롭다운 */
    :deep(.suggestion-div) {
        background: $white;
        border: 1px solid $gray-200;
        border-radius: 0;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.1);
    }

    :deep(.suggestion-header) {
        background: $gray-50;
        border-bottom: 1px solid $gray-100;

        .item {
            color: $gray-500;
            font-size: 0.75rem;
            font-weight: 700;
        }
    }

    :deep(.list-item) {
        .s_code { color: $gray-400; }
        .s_name { color: $gray-900; }
        .s_type { color: $gray-400; }

        &:hover { background: $gray-50; }
    }
}

/* ── body-box ── */
.body-box {
    display: flex;
    flex-direction: column;
    gap: 16px;
}

/* ── 공통: 섹션 헤더 ── */
.section-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 12px;

    .section-icon {
        font-size: 0.95rem;
    }

    .section-title {
        text-align: start;
        font-size: 0.95rem;
        font-weight: 700;
        color: $gray-900;
        flex: 1;
    }

    .section-badge {
        font-size: 0.68rem;
        font-weight: 700;
        color: $navy;
        background: #efefef;
        border: 1px solid #c4c4c4;
        padding: 2px 8px;
        border-radius: 0;
    }

    .token-info {
        font-size: 0.65rem;
        font-weight: 500;
        color: $gray-400;
        background: $gray-50;
        border: 1px solid $gray-100;
        padding: 2px 7px;
        border-radius: 0;
        white-space: nowrap;
        font-variant-numeric: tabular-nums;
    }

    .section-unit {
        font-size: 0.72rem;
        color: $gray-400;
    }

    .ai-refresh-btn {
        flex-shrink: 0;
        padding: 4px 10px;
        border: 1px solid $gray-200;
        background: $white;
        color: $gray-700;
        font-size: 0.72rem;
        font-weight: 600;
        cursor: pointer;
        white-space: nowrap;
        transition: border-color .15s, color .15s;

        &:hover:not(:disabled) { border-color: $blue; color: $blue; }
        &:disabled { color: $gray-400; cursor: not-allowed; }
    }
}

/* ── ① AI 분석 결과 섹션 ── */
.ai-result-section {
    background: $white;
    border: 1px solid $gray-200;
    border-radius: 0;
    padding: 18px 16px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);

    .ai-result-body {
        // min-height: 80vw; /* 모바일 기준 화면 폭의 80% → 세로 큰 공간 */
        max-height: 50vh;
        display: flex;
        flex-direction: column;
        justify-content: flex-start;

        @media (min-width: 600px) {
            min-height: 400px;
        }

        /* 3개 섹션으로 나뉘며 공간을 덜 차지하도록 축소 */
        &.compact {
            max-height: 40vh;

            @media (min-width: 600px) {
                min-height: 160px;
            }
        }
    }

    .ai-empty {
        display: flex;
        align-items: center;
        justify-content: center;
        flex: 1;
        padding: 24px 0;
        font-size: 0.85rem;
        color: $gray-400;
    }

    /* ── marked 렌더링 영역 ── */
    .markdown-body {
        overflow: scroll;
        text-align: start;
        font-size: 0.9rem;
        line-height: 1.8;
        color: $gray-700;
        word-break: keep-all;

        :deep(h1), :deep(h2) {
        font-size: 0.95rem;
            font-weight: 700;
            color: $navy;
            margin: 18px 0 6px;
            padding-bottom: 5px;
            border-bottom: 1px solid $gray-100;
        }

        :deep(h3) {
            font-size: 0.88rem;
            font-weight: 700;
            color: $gray-900;
            margin: 14px 0 4px;
        }

        :deep(p) {
            margin: 6px 0;
        color: $gray-700;
        }

        :deep(ul), :deep(ol) {
            padding-left: 18px;
            margin: 6px 0;

            li {
                font-size: 0.88rem;
                line-height: 1.7;
                color: $gray-700;
            }
        }

        :deep(strong) {
            font-weight: 700;
            color: $gray-900;
        }

        :deep(code) {
            background: $gray-50;
            border: 1px solid $gray-100;
            border-radius: 0;
            padding: 1px 5px;
            font-size: 0.82rem;
            color: $navy;
        }

        :deep(pre) {
            background: $gray-50;
            border: 1px solid $gray-100;
            border-radius: 0;
            padding: 12px 14px;
            overflow-x: auto;

            code {
                border: none;
                padding: 0;
                background: none;
            }
        }

        :deep(blockquote) {
            border-left: 3px solid $blue;
            margin: 8px 0;
            padding: 4px 12px;
            color: $gray-500;
            background: $gray-50;
            border-radius: 0;
        }

        :deep(table) {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.82rem;
            margin: 10px 0;

            th {
                background: $gray-50;
                color: $gray-500;
                font-weight: 700;
                padding: 7px 8px;
                border: 1px solid $gray-100;
                text-align: center;
            }

            td {
                padding: 7px 8px;
                border: 1px solid $gray-100;
                color: $gray-700;
                text-align: right;

                &:first-child { text-align: left; }
            }

            tr:nth-child(even) td { background: $gray-50; }
        }

        /* 첫 번째 h2 상단 여백 제거 */
        :deep(> h1:first-child),
        :deep(> h2:first-child) { margin-top: 0; }
    }

    .ai-loading {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        flex: 1;
        gap: 14px;

        .loading-dots {
            display: flex;
            gap: 8px;

            span {
                width: 8px;
                height: 8px;
                background: $blue;
                border-radius: 0;
                animation: bounce 1.2s infinite ease-in-out;

                &:nth-child(2) { animation-delay: 0.2s; }
                &:nth-child(3) { animation-delay: 0.4s; }
            }
        }

        .loading-label {
            font-size: 0.85rem;
            color: $gray-500;
        }
    }
}

/* ── ② 분기 실적 ── */
.quarterly-section {
    background: $white;
    border: 1px solid $gray-200;
    border-radius: 0;
    padding: 18px 16px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}

.quarterly-table {
    border: 1px solid $gray-100;
    border-radius: 0;
    overflow: hidden;

    .qt-row {
        display: grid;
        grid-template-columns: 5.5rem repeat(4, 1fr);
        border-bottom: 1px solid $gray-100;

        &.qt-head {
            background: $gray-50;

            .qt-cell {
                font-size: 0.72rem;
                font-weight: 700;
                color: $gray-500;
            }
        }

        &.last {
            border-bottom: none;
        }
    }

    .qt-cell {
        padding: 9px 4px;
        text-align: center;
        font-size: 0.8rem;
        color: $gray-700;

        &.label-col {
            text-align: left;
            padding-left: 10px;
            font-size: 0.78rem;
            font-weight: 600;
            color: $gray-500;
            background: $gray-50;
            border-right: 1px solid $gray-100;
        }

        &.num {
            font-weight: 600;
            font-size: 0.82rem;
        }
    }

    .val-up   { color: $red; }
    .val-down { color: $navy; }
}

/* ── ③ 추천 성과 ── */
.rec-section {
    background: $white;
    border: 1px solid $gray-200;
    border-radius: 0;
    padding: 18px 16px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}

.rec-date-badge {
    font-size: 0.72rem;
    color: $gray-500;
    background: $gray-100;
    border: 1px solid $gray-200;
    padding: 2px 8px;
    border-radius: 0;
}

.rec-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 10px;
}

.rec-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
    padding: 14px 8px;
    border-radius: 0;
    border: 1px solid $gray-100;
    background: $gray-50;
    text-align: center;

    &.base-card {
        border-color: $gray-200;
    }

    &.high-card {
        border-color: #c4c4c4;
        background: #fafafa;
    }

    .rec-label {
        font-size: 0.68rem;
        font-weight: 600;
        color: $gray-500;
        line-height: 1.3;
    }

    .rec-price {
        font-size: 1rem;
        font-weight: 800;
        color: $gray-900;
        line-height: 1.2;

        em {
            font-size: 0.7rem;
            font-weight: 500;
            color: $gray-500;
            font-style: normal;
            margin-left: 1px;
        }
    }
}

.rec-rate-badge {
    font-size: 0.72rem;
    font-weight: 700;
    padding: 3px 8px;
    border-radius: 0;

    &.neutral  { background: $gray-100; color: $gray-500; }
    &.rate-up  { background: #efefef; color: $red; }
    &.rate-down{ background: #efefef; color: $navy; }
}

/* ── 전환 애니메이션 ── */
.fade-slide-enter-active,
.fade-slide-leave-active {
    transition: opacity 0.3s ease, transform 0.3s ease;
}
.fade-slide-enter-from {
    opacity: 0;
    transform: translateY(16px);
}
.fade-slide-leave-to {
    opacity: 0;
}

/* ── 로딩 바운스 ── */
@keyframes bounce {
    0%, 80%, 100% { transform: scale(0.7); opacity: 0.4; }
    40%           { transform: scale(1);   opacity: 1; }
}
</style>
