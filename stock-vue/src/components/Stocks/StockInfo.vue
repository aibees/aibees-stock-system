<template>
    <div id="stock-analysis">
        <BrandHeader :title="title" />

        <div class="contents">
            <!-- 검색 섹션 -->
            <section class="search-section">
                <SAutoInput
                id="search-input"
                v-model:name="inputName"
                v-model:code="inputCode"
                @search="stockSearchHandler"
                width="100%" />
                <!-- 차트 이동은 하단 고정 바의 "차트 보기" 버튼이 맡는다 -->
            </section>

            <transition name="fade-slide">
                <div v-if="stockDetail" class="body-box">

                    <!-- ═══ 종목 요약 헤더: 이름/코드 + (추천 행이 있으면) 현재가·등락·장 상태 ═══ -->
                    <section class="stock-head">
                        <div class="sh-who">
                            <span class="sh-name">{{ item?.stock_name || inputName }}</span>
                            <span class="sh-code">{{ inputCode }}</span>
                        </div>
                        <div v-if="item" class="sh-px">
                            <span class="sh-price">{{ formatNumber(item.close) }}</span>
                            <span class="sh-chg" :class="chg.cls">{{ chg.text }}</span>
                        </div>
                        <div v-if="item" class="sh-status" :class="status.state"><i class="dot"></i>{{ status.label }}</div>
                    </section>

                    <!-- ═══ 탭: 분석내용(재무+조건) / AI 견해 ═══ -->
                    <div class="tabs" role="tablist" aria-label="종목 상세">
                        <button v-for="t in TABS" :key="t.key" type="button" role="tab" class="tab-btn"
                            :class="{ on: tab === t.key }" :aria-selected="tab === t.key ? 'true' : 'false'" @click="tab = t.key">
                            {{ t.label }}
                        </button>
                    </div>

                    <!-- ───────────── AI 견해 탭(기업개요·테마·뉴스·추천 이력) ───────────── -->
                    <div v-show="tab === 'basis'" class="tab-panel" role="tabpanel">

                    <!-- ① 기업개요 + 재무현황 (버튼 갱신, 실적발표월만) -->
                    <section class="ai-result-section">
                        <div class="section-header">
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

                    <!-- 봉 모양: 매수추천 펼침 행과 같은 DayCandle(그날 시/고/저/종 + 거래량, 장중엔 '현재가') -->
                    <section v-if="item" class="ai-result-section">
                        <div class="section-header">
                            <span class="section-title">봉 모양</span>
                            <span class="token-info">{{ itemDateLabel }} 기준</span>
                        </div>
                        <DayCandle class="flat-candle" :open="item.open" :high="item.high" :low="item.low" :close="item.close"
                            :volume="item.volume" :close-label="status.state === 'live' ? '현재가' : '종가'" />
                    </section>

                    <!-- 충족한 신호: 칩 나열 대신 체크 + 이름 + 한 줄 설명의 목록(전체 조건은 분석내용 탭) -->
                    <section v-if="item" class="ai-result-section">
                        <div class="section-header">
                            <span class="section-title">충족한 신호</span>
                            <span class="sig-count"><b>{{ cond.pass }}</b> / {{ cond.total }}</span>
                        </div>
                        <ul v-if="passedSignals.length" class="sig-list">
                            <li v-for="r in passedSignals" :key="r.label">
                                <span class="sig-mark" aria-hidden="true">✓</span>
                                <div class="sig-body">
                                    <div class="sig-name">{{ r.short }}</div>
                                    <div class="sig-desc">{{ r.desc }}</div>
                                </div>
                            </li>
                        </ul>
                        <p v-else class="muted">아직 충족한 신호가 없어요. 전체 조건은 분석내용 탭에서 볼 수 있어요.</p>
                    </section>
                    <section v-else-if="itemLoaded" class="ai-result-section">
                        <p class="muted">이 날짜의 추천 목록에 없는 종목이라 차트 모양·신호 정보가 없어요.</p>
                    </section>

                    <!-- ② 현재 테마 (버튼 갱신, 주 1회 권장) -->
                    <section class="ai-result-section">
                        <div class="section-header">
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

                    </div><!-- /AI 견해 탭 -->

                    <!-- ───────────── 분석내용 탭: 재무 + 조건 ───────────── -->
                    <div v-show="tab === 'analysis'" class="tab-panel" role="tabpanel">
                        <section class="an-section">
                            <!-- 기준: PER·PBR 은 현재가 ÷ 결산 EPS/BPS, ROE·증가율은 그 결산 기준(KIS 재무비율) -->
                            <div class="an-head">
                                <h3 class="an-title">재무</h3>
                                <span v-if="fin" class="an-basis">{{ fin.settle_ym || '-' }} 결산 · 한국투자증권</span>
                            </div>
                            <template v-if="fin">
                                <!-- 판별조건과 같은 체크 목록 — 저평가·적합(pass)이면 노란 체크 -->
                                <ul class="cond-list fin-list">
                                    <li v-for="r in finRows" :key="r.label" :class="{ ok: r.pass === true }">
                                        <span class="mark" aria-hidden="true">{{ r.pass === true ? '✓' : '–' }}</span>
                                        <div class="fin-body">
                                            <div class="fin-line">
                                                <span class="fin-label">{{ r.label }}</span>
                                                <span class="fin-right">
                                                    <span class="fin-value">{{ r.value ?? '-' }}</span>
                                                    <span class="verdict" :class="r.pass === true ? 'ok' : (r.pass === false ? 'ng' : 'na')">{{ r.verdict }}</span>
                                                </span>
                                            </div>
                                            <span class="fin-desc">{{ r.desc }}</span>
                                        </div>
                                    </li>
                                </ul>
                            </template>
                            <p v-else-if="finError" class="muted card-empty">
                                {{ finError }} <button type="button" class="link-btn" @click="loadFin(stockDetail.code, true)">다시 시도</button>
                            </p>
                            <p v-else class="muted card-empty">불러오는 중입니다…</p>
                        </section>

                        <section class="an-section">
                            <h3 class="an-title">판별조건</h3>
                            <template v-if="item">
                                <div class="cond-head">
                                    <strong>조건 충족 {{ cond.pass }}/{{ cond.total }}개</strong>
                                </div>
                                <ul class="cond-list">
                                    <li v-for="r in condRows" :key="r.label" :class="{ ok: r.pass }">
                                        <span class="mark" aria-hidden="true">{{ r.pass ? '✓' : '–' }}</span>
                                        <div class="cond-body">
                                            <div class="cond-name">{{ r.label }}<span class="cond-state">{{ r.pass ? '충족' : '미충족' }}</span></div>
                                            <div class="cond-desc">{{ r.desc }}</div>
                                        </div>
                                    </li>
                                </ul>
                                <!-- 점수는 장 마감 후 산출된다 — 값이 있을 때만 보여준다 -->
                                <p v-if="hasValue(item.score)" class="basis-note">종합 점수 {{ numOrNull(item.score) }} / 100</p>
                            </template>
                            <p v-else class="muted card-empty">{{ itemLoaded ? '이 날짜의 추천 목록에 없는 종목이라 판별조건 정보가 없어요.' : '불러오는 중입니다…' }}</p>
                        </section>
                    </div>

                    <p class="disclaimer">본 정보는 투자 권유가 아니며, 투자 판단의 책임은 투자자 본인에게 있습니다.</p>

                    <!-- ═══ 하단 고정 버튼 ═══ -->
                    <div class="action-bar">
                        <button type="button" class="act primary" @click="goToChart">차트 보기</button>
                    </div>
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
import {
    numOrNull, formatNumber as fmtNum, hasValue, changeInfo, fundamentalRows, technicalRows,
    conditionCount, kstNowParts, marketStatus, getLatestBatchDate,
} from '@scripts/stockSignals.js';

// marked 옵션
marked.setOptions({ breaks: true, gfm: true });

const route = useRoute();
const router = useRouter();
const title = ref('종목 심층 분석');
const stockDetail = ref(null);
const inputName = ref('');
const inputCode = ref('');

const userSession = assUserSession();

/* ── 탭 / 추천 행(item) ──
 * 근거·재무·조건 정보는 /stocks/buy-target 의 한 행에서 나온다(홈과 같은 데이터·판정 로직).
 * 홈에서 들어오면 query.ymd 로 같은 날짜의 행을 찾고, 직접 검색해 들어오면 최신 배치일을 쓴다.
 * 그 날짜 추천 목록에 없는 종목이면 item 이 null — 해당 탭은 안내 문구를 보여준다. */
const TABS = [
    { key: 'analysis', label: '분석내용' },   // 재무 + 조건
    { key: 'basis',    label: 'AI 견해' },     // 기업개요·테마·뉴스·추천 이력
];
const tab = ref('analysis');
const item = ref(null);
const itemLoaded = ref(false);

const status = computed(() => {
    const ymd = item.value?.ymd;
    const dash = ymd ? `${ymd.slice(0, 4)}-${ymd.slice(4, 6)}-${ymd.slice(6, 8)}` : getLatestBatchDate();
    return marketStatus(dash, kstNowParts());
});
const chg = computed(() => (item.value ? changeInfo(item.value) : { cls: 'flat', text: '' }));
const cond = computed(() => (item.value ? conditionCount(item.value) : { pass: 0, total: 0 }));
const condRows = computed(() => (item.value ? technicalRows(item.value) : []));
/* ── 재무 탭: 진입할 때 KIS 에서 조회(추천 목록에 없는 종목도). 종목당 한 번 — 서버도 10분 기억한다. ── */
const fin = ref(null);
const finError = ref('');
let finCode = null;
const loadFin = async (code, force = false) => {
    if (!code || (!force && finCode === code)) return;
    finCode = code;
    fin.value = null;
    finError.value = '';
    try {
        const { data } = await aibeesApi.get(`/api/v1/stocks/id/${encodeURIComponent(code)}/finance`);
        if (!data?.success) throw new Error(data?.error?.message);
        if (finCode === code) fin.value = data.data;
    } catch (e) {
        if (finCode === code) finError.value = e?.response?.data?.error?.message || e?.message || '재무 지표를 불러오지 못했어요.';
    }
};
watch(tab, (t) => { if (t === 'analysis') loadFin(stockDetail.value?.code); });
const finRows = computed(() => (fin.value ? fundamentalRows(fin.value) : []));
const passedSignals = computed(() => condRows.value.filter(r => r.pass));
const itemDateLabel = computed(() => {
    const y = item.value?.ymd;
    return y ? `${y.slice(4, 6)}/${y.slice(6, 8)}` : '';
});

const loadItem = async (code) => {
    item.value = null;
    itemLoaded.value = false;
    const ymd = String(route.query.ymd || getLatestBatchDate().replaceAll('-', ''));
    try {
        const { data } = await aibeesApi.get('/api/v1/stocks/buy-target', { params: { ymd } });
        item.value = (data?.data ?? []).find(r => r.stock_code === code) ?? null;
    } catch (e) {
        console.error(e);
    } finally {
        itemLoaded.value = true;
    }
};

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
    router.push({ path: '/stock/chart', query: { code: inputCode.value } });
};

const stockSearchHandler = (code) => {
    if (!code) return;
    stockDetail.value = { code };
    tab.value = 'analysis';
    finCode = null;      // 종목이 바뀌면 재무를 새로 조회(첫 탭이 분석내용이라 바로 부른다)
    fin.value = null;
    finError.value = '';
    loadFin(code);
    loadItem(code);
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

const formatNumber = (v) => fmtNum(v);
const formatRate = (v) => (v > 0 ? '+' : '') + v.toFixed(2) + '%';
</script>

<style scoped lang="scss">
/* ── 색상 변수: 양봉상회 토큰(홈·매수추천과 동일). 변수명은 유지하고 값만 브랜드 톤으로 ── */
$white:    #ffffff;
$gray-50:  #FFFDF5;
$gray-100: #F3EAD2;
$gray-200: #EFE2BC;
$gray-300: #EAD9A6;
$gray-400: #9A8C7E;
$gray-500: #6B5B4E;
$gray-700: #4A3628;
$gray-900: #2B1D14;
$blue:     #7A4423;
$navy:     #7A4423;
$red:      #C8282A;
$amber:    #A0662F;

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

/* ── 공통: 섹션 헤더 — 제목은 한 줄 유지, 공간이 모자라면 업데이트 시각·버튼이 다음 줄로 ── */
.section-header {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 4px 8px;
    margin-bottom: 12px;

    .section-icon {
        font-size: 0.95rem;
    }

    .section-title {
        text-align: start;
        font-size: 17px;
        font-weight: 700;
        color: $gray-900;
        flex: 1 0 auto;
        white-space: nowrap;
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
        font-size: 12px;
        font-weight: 500;
        color: $gray-400;
        white-space: nowrap;
        font-variant-numeric: tabular-nums;
    }

    .section-unit {
        font-size: 0.72rem;
        color: $gray-400;
    }

    .ai-refresh-btn {
        flex-shrink: 0;
        min-height: 32px;
        padding: 0 10px;
        border: 1px solid $gray-300;
        border-radius: 8px;
        background: $white;
        color: $blue;
        font-family: inherit;
        font-size: 12px;
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
                border-radius: 4px;
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
    font-size: 12px;
    color: $gray-500;
}

// 세 값은 박스 없이 세로 구분선으로만 나눈다
.rec-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
}

.rec-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
    padding: 6px 8px;
    text-align: center;
    border-left: 1px solid $gray-200;

    &:first-child { border-left: 0; }

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
    font-size: 13px;
    font-weight: 700;

    &.neutral  { color: $gray-500; }
    &.rate-up  { color: #C8282A; }
    &.rate-down{ color: #1F5BD1; }
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

/* ════════════════════════════════════════════════════════════════
 * 양봉상회 상세 화면 테마 (홈과 같은 토큰). 아래 규칙이 위의 기본 규칙을 덮어쓴다.
 * ════════════════════════════════════════════════════════════════ */
$yb-bg:     #FFFBEA;
$yb-bar:    #FFF6D2;
$yb-line:   #EFE2BC;
$yb-line-2: #EAD9A6;
$yb-brown:  #7A4423;
$yb-brown-d:#4A2814;
$yb-yellow: #FFC20E;
$yb-ink:    #2B1D14;
$yb-sub:    #6B5B4E;
$yb-up:     #D12B2B;
$yb-down:   #1F5BD1;

#stock-analysis :deep(.search-btn) {
    background: $yb-yellow;
    color: #3A200F;
    font-weight: 700;
    border-radius: 8px;
}
#stock-analysis :deep(.search-bar) {
    border-radius: 14px;
    border-color: $yb-line-2;
    background: #fff;
    box-shadow: none;
}
#stock-analysis :deep(.search-bar .search-icon) { display: none; }   // 돋보기 이모지는 다른 화면과 맞춰 숨긴다
#stock-analysis :deep(.search-bar input) { font-size: 16px; }         // iOS 포커스 확대 방지

#stock-analysis {
    background: #fff;
    color: $yb-ink;
    font-variant-numeric: tabular-nums;
    text-align: left;
}
.contents { padding-bottom: calc(112px + env(safe-area-inset-bottom, 0px)); }

// 섹션은 카드 없이 위쪽 구분선 + 제목으로만 나눈다(홈·트레이드와 같은 방식)
.ai-result-section,
.rec-section {
    background: transparent;
    border: 0;
    border-top: 1px solid $yb-line;
    border-radius: 0;
    box-shadow: none;
    padding: 16px 0 4px;
    margin: 0;
}
.section-header .section-title { color: $yb-ink; }
.ai-refresh-btn { border-radius: 8px; }

.body-box { display: flex; flex-direction: column; gap: 12px; }

/* ── 종목 요약 헤더 ── */
.stock-head {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 4px 12px;
    align-items: end;
    padding: 4px 2px 0;

    .sh-who { display: flex; align-items: baseline; gap: 8px; min-width: 0; }
    .sh-name { font-size: 22px; font-weight: 700; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .sh-code { font-size: 13px; color: #7A6B5D; }
    .sh-px { display: flex; flex-direction: column; align-items: flex-end; gap: 2px; }
    .sh-price { font-size: 22px; font-weight: 700; }
    .sh-chg {
        font-size: 13px;
        font-weight: 600;
        &.up { color: $yb-up; }
        &.down { color: $yb-down; }
        &.flat { color: $yb-sub; }
    }
    .sh-status {
        grid-column: 1 / -1;
        display: inline-flex;
        align-items: center;
        gap: 6px;
        font-size: 12px;
        color: $yb-sub;
        .dot { width: 7px; height: 7px; border-radius: 4px; background: #9A8F84; }
        &.live .dot { background: #E07A00; }
    }
}

/* ── 탭 ── */
.tabs {
    // 탭 개수만큼 전체 폭을 똑같이 나눈다(오른쪽 빈칸 없이)
    display: grid;
    grid-auto-flow: column;
    grid-auto-columns: minmax(0, 1fr);
    border-bottom: 1px solid $yb-line-2;
    margin-top: 4px;

    .tab-btn {
        min-height: 44px;
        border: 0;
        border-bottom: 3px solid transparent;
        background: transparent;
        color: $yb-sub;
        font-size: 15px;
        font-family: inherit;
        cursor: pointer;
        em { font-style: normal; font-size: 13px; margin-left: 4px; }

        &.on {
            color: $yb-brown;
            font-weight: 700;
            border-bottom-color: $yb-yellow;
        }
    }
}
.tab-panel { display: flex; flex-direction: column; gap: 12px; }
// 분석내용 탭: 재무 / 조건 두 묶음 — 카드 없이 소제목 + 구분선으로 나눈다
.an-section { display: flex; flex-direction: column; gap: 10px; }
.an-section + .an-section { margin-top: 8px; padding-top: 16px; border-top: 1px solid #EFE2BC; }
.an-title { margin: 0; font-size: 15px; font-weight: 700; color: #2B1D14; }
.an-head { display: flex; align-items: baseline; justify-content: space-between; gap: 10px; }
.an-basis { font-size: 11px; color: #7A6B5D; white-space: nowrap; }
// 탭 밑줄 바로 아래라 첫 섹션의 위쪽 구분선은 겹쳐 보인다 — 빼고 간격만 둔다
.tab-panel > section:first-child { border-top: 0; padding-top: 6px; }

.muted { margin: 0; font-size: 13px; color: $yb-sub; line-height: 1.5; }
.card-empty { padding: 28px 0; text-align: center; }
.link-btn { margin-left: 6px; padding: 0; border: 0; background: none; color: #7A4423; font: inherit; font-weight: 600; text-decoration: underline; cursor: pointer; }

/* ── 봉 모양: DayCandle 의 자체 테두리 박스는 이 화면에서만 걷어낸다(카드 최소화) ── */
// 루트 요소에는 부모 scope 속성이 붙으므로 :deep 없이 잡힌다. 섹션 클래스를 앞에 둬 DayCandle 자체 규칙보다 우선.
.ai-result-section .flat-candle { border: 0; border-radius: 0; padding: 0; background: transparent; }

/* ── 충족한 신호: 체크 + 이름 + 한 줄 설명 ── */
.sig-count {
    font-size: 14px;
    color: $yb-sub;
    b { font-size: 20px; font-weight: 700; color: $yb-brown; margin-right: 1px; }
}
.sig-list {
    margin: 0;
    padding: 0;
    list-style: none;

    li {
        display: grid;
        grid-template-columns: 24px minmax(0, 1fr);
        gap: 10px;
        padding: 10px 0;
        border-top: 1px solid $yb-line;
        &:first-child { border-top: 0; padding-top: 2px; }
    }
    .sig-mark {
        width: 22px; height: 22px; margin-top: 1px; border-radius: 11px;
        display: inline-flex; align-items: center; justify-content: center;
        background: $yb-yellow; color: $yb-brown-d; font-size: 12px; font-weight: 700;
    }
    .sig-name { font-size: 15px; font-weight: 700; color: $yb-ink; }
    .sig-desc { margin-top: 2px; font-size: 13px; line-height: 1.5; color: $yb-sub; }
}

/* ── 분석내용 탭 · 재무: 판별조건(.cond-list)과 같은 체크 목록. 한 줄에 "지표명 | 값 + 판정", 그 아래 작은 설명 ── */
.fin-list li { padding: 10px 0; align-items: start; }
.fin-body { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
.fin-line { display: flex; align-items: center; justify-content: space-between; gap: 10px; min-height: 24px; }
.fin-label { font-size: 14px; font-weight: 700; color: $yb-ink; }
.fin-right { display: inline-flex; align-items: center; gap: 8px; flex-shrink: 0; }
.fin-value { font-size: 16px; font-weight: 700; font-variant-numeric: tabular-nums; }
.fin-desc { font-size: 11px; line-height: 1.4; color: $yb-sub; }
// 판정은 색만이 아니라 글자("적합/높음/…")로도 구분한다
.verdict {
    flex-shrink: 0;
    padding: 2px 8px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 700;
    &.ok { background: $yb-bar; color: #5C3118; border: 1px solid $yb-line-2; }
    &.ng { background: #FDECEC; color: #A32020; }
    &.na { background: #F1ECE2; color: $yb-sub; }
}
.basis-note { margin: 0; font-size: 12px; line-height: 1.5; color: #7A6B5D; }

/* ── 분석내용 탭 · 조건: 체크리스트 ── */
.cond-head {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 4px 0 2px;
    strong { font-size: 15px; }
}
.cond-list {
    margin: 0;
    padding: 0;
    list-style: none;
    border-top: 1px solid $yb-line;

    li { display: grid; grid-template-columns: 28px minmax(0, 1fr); gap: 10px; padding: 14px 0; border-bottom: 1px solid $yb-line; }
    .mark {
        width: 24px; height: 24px; border-radius: 12px; display: inline-flex; align-items: center; justify-content: center;
        background: #F1ECE2; color: $yb-sub; font-weight: 700; font-size: 13px;
    }
    li.ok .mark { background: $yb-yellow; color: $yb-brown-d; }
    .cond-name { font-size: 14px; font-weight: 600; display: flex; align-items: center; gap: 8px; }
    .cond-state { font-size: 12px; font-weight: 700; color: $yb-sub; }
    li.ok .cond-state { color: $yb-brown; }
    .cond-desc { margin-top: 3px; font-size: 12px; line-height: 1.5; color: $yb-sub; }
}

.disclaimer { margin: 4px 0 0; font-size: 11px; line-height: 1.5; color: #7A6B5D; text-align: center; }

/* ── 하단 고정 버튼 (모바일에서는 하단 탭바 위) ── */
.action-bar {
    position: fixed;
    left: 0;
    right: 0;
    bottom: var(--lnb-total, 0px);
    z-index: 900;
    display: flex;
    gap: 8px;
    padding: 10px 16px;
    background: $yb-bar;
    border-top: 1px solid $yb-line-2;

    .act {
        flex: 1;
        min-height: 48px;
        border-radius: 12px;
        font-size: 15px;
        font-weight: 700;
        font-family: inherit;
        cursor: pointer;
        &.primary { border: 0; background: $yb-yellow; color: #3A200F; }
    }

    // 데스크톱: 하단 탭바가 없으므로 화면 맨 아래, 내용 폭에 맞춘다
    @media (min-width: 640px) {
        bottom: 0;
        padding-left: calc(50% - 284px);
        padding-right: calc(50% - 284px);
    }
}
</style>
