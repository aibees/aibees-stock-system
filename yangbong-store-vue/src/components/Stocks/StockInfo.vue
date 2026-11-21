<template>
    <div id="stock-analysis">
        <BrandHeader :title="title" back="/stock" />

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

                    <!-- ═══ 종목 요약 + 탭 (한 장의 흰 판): 이름/코드 + (추천 행이 있으면) 현재가·등락·장 상태 ═══ -->
                    <div class="top-card">
                    <section class="stock-head">
                        <div class="sh-who">
                            <span class="sh-name">{{ item?.stock_name || inputName }}</span>
                            <span class="sh-code">{{ inputCode }}</span>
                        </div>
                        <div v-if="item" class="sh-px">
                            <span class="sh-price">{{ formatNumber(item.close) }}</span>
                            <span class="sh-chg badge" :class="chg.cls">{{ chg.text }}</span>
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
                    </div><!-- /top-card -->

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
                        <!-- 봉 해석: AI 없이 정해진 규칙(몸통·꼬리 비율, 직전 봉, 거래량)으로 자동 판독 -->
                        <div v-if="candleRead" class="candle-read">
                            <p class="cr-head">
                                <span class="badge" :class="candleRead.tone">{{ CR_TONE[candleRead.tone] }}</span>
                                <span class="cr-text">{{ candleRead.head }}</span>
                            </p>
                            <ul v-if="candleRead.lines.length" class="cr-list">
                                <li v-for="ln in candleRead.lines" :key="ln">{{ ln }}</li>
                            </ul>
                            <p class="cr-note">정해진 규칙으로 자동 판독한 설명이에요(AI 아님). 투자 권유가 아니에요.</p>
                        </div>
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
                        <p class="muted">이 날짜의 주목 종목에 없는 종목이라 차트 모양·신호 정보가 없어요.</p>
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

                    <!-- ③ 선정 후 성과 추적 (최근 1달 이내 추천된 경우) -->
                    <section class="rec-section" v-if="recommendationData?.rec_record && recommendationData?.now_record && recommendationData?.max_record">
                        <div class="section-header">
                            <span class="section-title">선정 후 성과 추적</span>
                            <span class="rec-date-badge">선정일 {{ recommendationData.rec_record.ymd }}</span>
                        </div>
                        <div class="rec-grid">
                            <div class="rec-card base-card">
                                <span class="rec-label">선정일 종가 {{ recommendationData.rec_record.ymd }}</span>
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
                                <span class="rec-label">선정 후 최고가 {{ recommendationData.max_record.ymd }}</span>
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
                            <p v-else class="muted card-empty">{{ itemLoaded ? '이 날짜의 주목 종목에 없는 종목이라 판별조건 정보가 없어요.' : '불러오는 중입니다…' }}</p>
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
import { addRecent } from '@scripts/recentStocks.js';
import { assUserSession } from '@scripts/stores/user-stores';
import {
    numOrNull, formatNumber as fmtNum, hasValue, changeInfo, fundamentalRows, technicalRows,
    conditionCount, kstNowParts, marketStatus, getLatestBatchDate, candleReading,
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
const candleRead = computed(() => (item.value ? candleReading(item.value) : null));
const CR_TONE = { up: '강세 해석', down: '약세 해석', flat: '중립' };
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
    addRecent(code, inputName.value);   // 주식분석 대시보드의 "최근 본 회사"
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
        // 한도 초과(429)·쿨다운·실적발표월 제한은 서버 문구를 그대로 보여 준다.
        alert(e?.response?.data?.error?.message || 'AI 분석을 새로 만들지 못했어요. 잠시 후 다시 시도해 주세요.');
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
        // 한도 초과(429)·쿨다운·실적발표월 제한은 서버 문구를 그대로 보여 준다.
        alert(e?.response?.data?.error?.message || 'AI 분석을 새로 만들지 못했어요. 잠시 후 다시 시도해 주세요.');
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
@use '@@/_home-tokens.scss' as *;

/* 2026-11-21 홈(HomeSimple)과 같은 톤으로 개편: 섹션 = 흰 판, 섹션 사이 = 연회색 띠($band-h).
 * 글자 위계 — 섹션 제목 20 / 항목 16 / 보조 13(회색) / 부가 12(연회색). 색은 등락에만, 꿀빛은 포인트(체크·탭·버튼)에만. */
#stock-analysis {
    min-height: 100vh;
    background: $band;
    color: $ink;
    text-align: left;
    font-family: $font-body;
    font-variant-numeric: tabular-nums;
    letter-spacing: -0.2px;
    -webkit-font-smoothing: antialiased;
}
button { font: inherit; letter-spacing: inherit; }

.contents {
    max-width: 640px;
    margin: 0 auto;
    display: flex;
    flex-direction: column;
    gap: $band-h;
    padding: 0 0 calc(112px + env(safe-area-inset-bottom, 0px));
}
.body-box { display: flex; flex-direction: column; gap: $band-h; }

/* ── 흰 판(섹션) ── */
.search-section,
.top-card,
.ai-result-section,
.rec-section,
.an-section {
    background: $card;
    padding: 28px $pad-x 20px;
}

/* ── 검색 — SAutoInput 겉모습만 덮어쓴다 ── */
.search-section {
    padding-top: 16px;
    padding-bottom: 16px;

    :deep(.auto-complete-container) { margin: 0; width: 100%; }
    :deep(.search-bar) {
        width: 100% !important;
        box-sizing: border-box;
        margin: 0 !important;
        padding: 6px 6px 6px 14px;
        background: $card;
        border: 1px solid $line;
        border-radius: $radius;
        box-shadow: none;
        transition: border-color .15s;
        &:focus-within { border-color: $honey-500; }
    }
    :deep(.search-bar .search-icon) { display: none; }
    :deep(.search-bar input) { color: $ink; font-size: 16px; &::placeholder { color: $sub-2; } }   // 16px: iOS 확대 방지
    :deep(.search-bar .search-btn) {
        min-height: 40px;
        padding: 0 16px;
        border-radius: 8px;
        background: $honey-300;
        color: $honey-ink;
        font-size: 14px;
        font-weight: 700;
        font-family: inherit;
        white-space: nowrap;
        &:active { transform: scale(.97); }
    }
    :deep(.suggestion-div) { background: $card; border: 1px solid $line; border-radius: $radius; box-shadow: 0 8px 24px rgba(0, 0, 0, .08); overflow: hidden; }
    :deep(.suggestion-header) { background: $bg; border-bottom: 1px solid $line; .item { color: $sub; font-size: 12px; font-weight: 700; } }
    :deep(.list-item) {
        .s_code, .s_type { color: $sub-2; }
        .s_name { color: $ink; }
        &:hover { background: $bg; }
    }
}

/* ── 종목 요약 + 탭 ── */
.top-card { padding: 24px 0 0; }
.stock-head {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 6px 12px;
    align-items: end;
    padding: 0 $pad-x;

    .sh-who { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
    .sh-name { font-size: 24px; font-weight: 700; letter-spacing: -0.6px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .sh-code { font-size: 13px; color: $sub; }
    .sh-px { display: flex; flex-direction: column; align-items: flex-end; gap: 6px; }
    .sh-price { font-size: 26px; font-weight: 700; letter-spacing: -0.6px; line-height: 1.1; }
    .sh-status {
        grid-column: 1 / -1;
        display: inline-flex;
        align-items: center;
        gap: 6px;
        font-size: 12px;
        color: $sub;
        .dot { width: 6px; height: 6px; border-radius: 3px; background: $sub-2; }
        &.live .dot { background: $honey-500; }
    }
}
// 등락 배지(홈과 같은 모양)
.badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    height: 24px;
    min-width: 62px;
    padding: 0 6px;
    border-radius: $radius-sm;
    font-size: 13px;
    font-weight: 600;
    white-space: nowrap;
    color: $sub;
    background: $band;
    &.up   { color: $up;   background: $up-bg; }
    &.down { color: $down; background: $down-bg; }
}

.tabs {
    // 탭 개수만큼 전체 폭을 똑같이 나눈다
    display: grid;
    grid-auto-flow: column;
    grid-auto-columns: minmax(0, 1fr);
    margin-top: 18px;
    border-bottom: 1px solid $line;

    .tab-btn {
        min-height: 48px;
        border: 0;
        border-bottom: 2px solid transparent;
        margin-bottom: -1px;
        background: transparent;
        color: $sub;
        font-size: 16px;
        cursor: pointer;
        &.on { color: $ink; font-weight: 700; border-bottom-color: $ink; }
        &:focus-visible { outline: 2px solid $honey-500; outline-offset: -2px; }
    }
}
.tab-panel { display: flex; flex-direction: column; gap: $band-h; }

/* ── 섹션 제목 ── 제목은 한 줄 유지, 공간이 모자라면 업데이트 시각·버튼이 다음 줄로 */
.section-header {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 4px 8px;
    margin-bottom: 12px;

    .section-title { flex: 1 0 auto; text-align: start; font-size: 20px; font-weight: 700; letter-spacing: -0.5px; white-space: nowrap; }
    .token-info { font-size: 12px; color: $sub; white-space: nowrap; }
    .rec-date-badge { font-size: 13px; color: $sub; }
    .ai-refresh-btn {
        flex-shrink: 0;
        min-height: 32px;
        padding: 0 12px;
        border: 1px solid $line;
        border-radius: 8px;
        background: $card;
        color: $sub-ink;
        font-size: 13px;
        font-weight: 600;
        cursor: pointer;
        white-space: nowrap;
        &:disabled { color: $sub-2; cursor: not-allowed; }
        @media (hover: hover) { &:hover:not(:disabled) { background: $bg; } }
    }
}
.an-head { display: flex; align-items: baseline; justify-content: space-between; gap: 10px; margin-bottom: 12px; }
.an-title { margin: 0; font-size: 20px; font-weight: 700; letter-spacing: -0.5px; }
.an-basis { font-size: 12px; color: $sub; white-space: nowrap; }
// 판별조건 섹션도 같은 제목 간격
.an-section > .an-title { margin-bottom: 12px; }
.an-section { display: flex; flex-direction: column; }

/* ── AI 견해: 기업개요·테마·뉴스(마크다운) ── */
.ai-result-section {
    .ai-result-body {
        max-height: 50vh;
        display: flex;
        flex-direction: column;
        justify-content: flex-start;
        @media (min-width: 600px) { min-height: 160px; }
        &.compact { max-height: 40vh; }
    }
    .ai-empty { display: flex; align-items: center; justify-content: center; flex: 1; padding: 24px 0; font-size: 14px; color: $sub; }

    .markdown-body {
        overflow-y: auto;
        text-align: start;
        font-size: 15px;
        line-height: 1.75;
        color: $sub-ink;
        word-break: keep-all;

        :deep(h1), :deep(h2) { margin: 18px 0 6px; font-size: 16px; font-weight: 700; color: $ink; }
        :deep(h3) { margin: 14px 0 4px; font-size: 15px; font-weight: 700; color: $ink; }
        :deep(p) { margin: 6px 0; }
        :deep(ul), :deep(ol) { padding-left: 18px; margin: 6px 0; li { font-size: 15px; line-height: 1.7; } }
        :deep(strong) { font-weight: 700; color: $ink; }
        :deep(code) { padding: 1px 5px; border-radius: 4px; background: $band; font-size: 13px; color: $ink; }
        :deep(pre) { padding: 12px 14px; border-radius: 8px; background: $band; overflow-x: auto; code { padding: 0; background: none; } }
        :deep(blockquote) { margin: 8px 0; padding: 8px 12px; border-left: 3px solid $honey-500; border-radius: 0 8px 8px 0; background: $honey-strip; color: $honey-ink; }
        :deep(table) {
            width: 100%;
            border-collapse: collapse;
            margin: 10px 0;
            font-size: 13px;
            th { padding: 8px; background: $band; color: $sub-ink; font-weight: 700; border: 1px solid $line; text-align: center; }
            td { padding: 8px; border: 1px solid $line; text-align: right; &:first-child { text-align: left; } }
        }
        :deep(> h1:first-child), :deep(> h2:first-child) { margin-top: 0; }
    }

    .ai-loading {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        flex: 1;
        gap: 14px;
        padding: 20px 0;
        .loading-dots { display: flex; gap: 8px; span { width: 8px; height: 8px; border-radius: 4px; background: $honey-500; animation: bounce 1.2s infinite ease-in-out; &:nth-child(2) { animation-delay: .2s; } &:nth-child(3) { animation-delay: .4s; } } }
        .loading-label { font-size: 14px; color: $sub; }
    }
}
// 봉 모양: DayCandle 자체 테두리 박스는 이 화면에서만 걷어낸다(루트에 부모 scope 속성이 붙어 :deep 없이 잡힌다)
.ai-result-section .flat-candle { border: 0; border-radius: 0; padding: 0; background: transparent; }

/* ── 봉 해석(규칙 기반 자동 판독) ── */
.candle-read { margin-top: 16px; padding: 14px 16px; border-radius: $radius; background: $honey-strip; }
.cr-head { display: flex; align-items: flex-start; gap: 8px; margin: 0; }
.cr-head .badge { flex: none; height: 22px; min-width: 0; margin-top: 1px; padding: 0 7px; font-size: 12px; background: $card; }
.cr-head .badge.up   { background: $up-bg; }
.cr-head .badge.down { background: $down-bg; }
.cr-text { font-size: 16px; font-weight: 700; line-height: 1.45; word-break: keep-all; }
.cr-list { margin: 10px 0 0; padding: 0; list-style: none; display: flex; flex-direction: column; gap: 6px; }
.cr-list li { position: relative; padding-left: 12px; font-size: 14px; line-height: 1.55; color: $honey-ink; word-break: keep-all; }
.cr-list li::before { content: ''; position: absolute; left: 0; top: 9px; width: 4px; height: 4px; border-radius: 2px; background: $amber-700; }
.cr-note { margin: 10px 0 0; font-size: 12px; line-height: 1.5; color: $sub; }

/* ── 충족한 신호 ── */
.sig-count {
    font-size: 14px;
    color: $sub;
    b { margin-right: 1px; font-size: 20px; font-weight: 700; color: $amber-700; }
}
.sig-list {
    margin: 0;
    padding: 0;
    list-style: none;
    li { display: grid; grid-template-columns: 24px minmax(0, 1fr); gap: 12px; padding: 12px 0; }
    .sig-mark {
        width: 22px; height: 22px; margin-top: 1px; border-radius: 11px;
        display: inline-flex; align-items: center; justify-content: center;
        background: $honey-dot; color: $honey-ink; font-size: 12px; font-weight: 700;
    }
    .sig-name { font-size: 16px; font-weight: 600; }
    .sig-desc { margin-top: 2px; font-size: 13px; line-height: 1.5; color: $sub; }
}

/* ── 분석내용 탭: 재무·판별조건 체크 목록(선 없이 여백으로 나눈다) ── */
.cond-head { padding: 0 0 4px; strong { font-size: 16px; font-weight: 700; } }
.cond-list {
    margin: 0;
    padding: 0;
    list-style: none;

    li { display: grid; grid-template-columns: 24px minmax(0, 1fr); gap: 12px; padding: 12px 0; }
    .mark {
        width: 22px; height: 22px; margin-top: 1px; border-radius: 11px;
        display: inline-flex; align-items: center; justify-content: center;
        background: $band; color: $sub-2; font-weight: 700; font-size: 12px;
    }
    li.ok .mark { background: $honey-dot; color: $honey-ink; }
    .cond-name { display: flex; align-items: center; gap: 8px; font-size: 16px; font-weight: 600; }
    .cond-state { font-size: 12px; font-weight: 700; color: $sub; }
    li.ok .cond-state { color: $amber-700; }
    .cond-desc { margin-top: 2px; font-size: 13px; line-height: 1.5; color: $sub; }
}
.fin-body { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
.fin-line { display: flex; align-items: center; justify-content: space-between; gap: 10px; min-height: 24px; }
.fin-label { font-size: 16px; font-weight: 600; }
.fin-right { display: inline-flex; align-items: center; gap: 8px; flex-shrink: 0; }
.fin-value { font-size: 16px; font-weight: 700; }
.fin-desc { font-size: 13px; line-height: 1.5; color: $sub; }
// 판정은 색만이 아니라 글자("적합/높음/…")로도 구분한다
.verdict {
    flex-shrink: 0;
    height: 22px;
    padding: 0 8px;
    border-radius: $radius-sm;
    display: inline-flex;
    align-items: center;
    font-size: 12px;
    font-weight: 700;
    &.ok { background: $honey-strip; color: $amber-700; }
    &.ng { background: $up-bg; color: $up; }
    &.na { background: $band; color: $sub; }
}
.basis-note { margin: 8px 0 0; font-size: 12px; line-height: 1.5; color: $sub; }

.muted { margin: 0; font-size: 14px; line-height: 1.5; color: $sub; }
.card-empty { padding: 24px 0; text-align: center; }
.link-btn { margin-left: 6px; padding: 0; border: 0; background: none; color: $sub-ink; font: inherit; font-weight: 600; text-decoration: underline; text-underline-offset: 3px; cursor: pointer; }

/* ── 선정 후 성과 추적: 꿀빛 띠 안에 세 값 ── */
.rec-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    padding: 14px 0;
    border-radius: $radius;
    background: $honey-strip;
}
.rec-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
    padding: 4px 8px;
    text-align: center;
    border-left: 1px solid $honey-100;
    &:first-child { border-left: 0; }

    .rec-label { font-size: 12px; font-weight: 500; line-height: 1.3; color: $sub; }
    .rec-price { font-size: 16px; font-weight: 700; line-height: 1.2; em { margin-left: 1px; font-size: 12px; font-weight: 500; font-style: normal; color: $sub; } }
}
.rec-rate-badge {
    font-size: 13px;
    font-weight: 700;
    &.neutral   { color: $sub; }
    &.rate-up   { color: $up; }
    &.rate-down { color: $down; }
}

/* ── 고지: 띠 색 바탕 위 작은 글자 ── */
.disclaimer { margin: 0; padding: 4px $pad-x 8px; font-size: 12px; line-height: 1.6; color: $sub; }

/* ── 전환·로딩 ── */
.fade-slide-enter-active, .fade-slide-leave-active { transition: opacity .3s ease, transform .3s ease; }
.fade-slide-enter-from { opacity: 0; transform: translateY(16px); }
.fade-slide-leave-to { opacity: 0; }
@keyframes bounce {
    0%, 80%, 100% { transform: scale(.7); opacity: .4; }
    40%           { transform: scale(1);  opacity: 1; }
}
@media (prefers-reduced-motion: reduce) {
    .fade-slide-enter-active, .fade-slide-leave-active { transition: none; }
    .ai-loading .loading-dots span { animation: none; }
}

/* ── 하단 고정 버튼 (모바일에서는 하단 탭바 위) ── */
.action-bar {
    position: fixed;
    left: 0;
    right: 0;
    bottom: var(--lnb-total, 0px);
    z-index: 900;
    display: flex;
    gap: 8px;
    padding: 10px $pad-x;
    background: $card;
    border-top: 1px solid $line;

    .act {
        flex: 1;
        min-height: 50px;
        border: 0;
        border-radius: $radius;
        font-size: 16px;
        font-weight: 700;
        cursor: pointer;
        &.primary { background: $honey-300; color: $honey-ink; }
        &:focus-visible { outline: 2px solid $honey-ink; outline-offset: 2px; }
    }

    // 데스크톱: 하단 탭바가 없으므로 화면 맨 아래, 내용 폭에 맞춘다
    @media (min-width: 640px) {
        bottom: 0;
        padding-left: calc(50% - 300px);
        padding-right: calc(50% - 300px);
    }
}
</style>
