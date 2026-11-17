<template>
    <div id="home-simple">

        <!-- ════════ 상단: 로고 + 처음이세요? + 계정 ════════ -->
        <header class="home-header" :class="{ scrolled }">
            <div class="hh-row">
                <button type="button" class="brand" @click="router.push('/home')" aria-label="양봉상회 홈">
                    <img class="brand-logo" src="/favicon.svg" alt="" aria-hidden="true" />
                    <span class="brand-name">양봉상회</span>
                </button>

                <div class="hh-actions">
                    <button type="button" class="guide-btn" @click="router.push(ONBOARDING_PATH)"><i class="dot" aria-hidden="true"></i>처음이세요?</button>
                    <div class="account" ref="accountRef">
                        <button v-if="isLoggedIn" type="button" class="icon-btn" :aria-label="`내 계정 · ${userName} 님`"
                            aria-haspopup="menu" :aria-expanded="menuOpen ? 'true' : 'false'" @click.stop="menuOpen = !menuOpen">
                            <span class="avatar">{{ userInitial }}</span>
                        </button>
                        <button v-else type="button" class="login-btn" @click="router.push('/login')">로그인</button>

                        <ul v-if="menuOpen" class="account-menu" role="menu">
                            <li class="am-name" aria-hidden="true">{{ userName }} 님</li>
                            <li role="menuitem"><button type="button" @click="goTo('/user-option')">개인설정</button></li>
                            <li role="menuitem"><button type="button" @click="goTo('/menu')">전체 메뉴</button></li>
                            <li role="menuitem"><button type="button" class="danger" @click="logout">로그아웃</button></li>
                        </ul>
                    </div>
                </div>
            </div>
        </header>

        <main class="home-main">

            <!-- ── 1. 시황: 시장 날씨 한 줄 + 코스피·코스닥·원/달러 리스트(2026-11-17 화이트 톤 개편) ── -->
            <section class="sec market" aria-labelledby="market-title">
                <div class="sec-head">
                    <h2 id="market-title">오늘 시장</h2>
                </div>
                <div v-if="weather" class="weather" :class="weather.key" role="status">
                    <span class="wx-box" aria-hidden="true">
                        <svg class="wx-icon" viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round">
                            <template v-if="weather.key === 'sunny'">
                                <circle cx="24" cy="24" r="8"></circle>
                                <path d="M24 6v5M24 37v5M6 24h5M37 24h5M11.3 11.3l3.5 3.5M33.2 33.2l3.5 3.5M11.3 36.7l3.5-3.5M33.2 14.8l3.5-3.5"></path>
                            </template>
                            <template v-else-if="weather.key === 'warm'">
                                <circle cx="19" cy="18" r="6"></circle>
                                <path d="M19 6v3M7 18h3M10.5 9.5l2 2M27.5 9.5l-2 2"></path>
                                <path d="M17 40h18a6.5 6.5 0 0 0 .6-13 9 9 0 0 0-17-2A7.6 7.6 0 0 0 17 40z"></path>
                            </template>
                            <template v-else-if="weather.key === 'cloudy'">
                                <path d="M14 36h20a7.5 7.5 0 0 0 .7-15 10.5 10.5 0 0 0-20-2.4A8.8 8.8 0 0 0 14 36z"></path>
                            </template>
                            <template v-else>
                                <path d="M14 30h20a7.5 7.5 0 0 0 .7-15 10.5 10.5 0 0 0-20-2.4A8.8 8.8 0 0 0 14 30z"></path>
                                <path d="M25 30l-5 8h6l-4 8"></path>
                            </template>
                        </svg>
                    </span>
                    <span class="wx-text">
                        <span class="wx-name">{{ weather.text }}</span>
                        <b class="wx-desc">{{ weather.desc }}</b>
                    </span>
                </div>
                <!-- 코스피·코스닥·원/달러: 카드 없이 같은 모양의 리스트 3줄(2026-11-17 심플 버전으로 되돌림) -->
                <ul class="rows">
                    <li v-for="m in indexCards" :key="m.key" class="row">
                        <span class="r-main">
                            <b class="r-name">{{ m.label }}</b>
                            <small class="r-sub">
                                <template v-for="(p, i) in m.periods" :key="p.label">{{ i ? ' · ' : '' }}{{ p.label }} <i :class="p.cls">{{ p.text }}</i></template>
                            </small>
                        </span>
                        <svg v-if="m.sparkPoints" class="r-spark" :class="m.sparkCls" viewBox="0 0 64 24" preserveAspectRatio="none" aria-hidden="true">
                            <polyline :points="m.sparkPoints" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke" />
                        </svg>
                        <span class="r-val">
                            <b>{{ m.priceText }}</b>
                            <small :class="m.todayCls">{{ m.todayText }}</small>
                        </span>
                    </li>
                    <li v-if="fxItem" class="row">
                        <span class="r-main">
                            <b class="r-name">원/달러</b>
                            <small class="r-sub">환율</small>
                        </span>
                        <span class="r-val">
                            <b>{{ fxItem.priceText }}</b>
                            <small :class="fxItem.cls">{{ fxItem.chgText }}</small>
                        </span>
                    </li>
                </ul>
            </section>

            <!-- ── 2. AI 분석 종목 TOP 3: 순위 리스트. 줄을 누르면 AI 분석, 아래 작은 글자 링크로 차트 ── -->
            <section class="sec watch" aria-labelledby="watch-title">
                <div class="sec-head">
                    <h2 id="watch-title">AI 분석 종목 TOP 3</h2>
                    <span v-if="basisText" class="meta">{{ basisText }}</span>
                </div>

                <div v-if="isLoading" class="w-skeleton" aria-busy="true" aria-label="불러오는 중">
                    <i v-for="n in 3" :key="n"></i>
                </div>
                <div v-else-if="!ordered.length" class="w-empty">
                    <p>오늘은 AI 기준에 충족된 종목이 없습니다.</p>
                    <button v-if="items.length" type="button" class="text-link" @click="router.push('/stock/preset')">설정 조정하기</button>
                </div>
                <ol v-else class="rows">
                    <li v-for="(w, i) in visibleRows" :key="w.code" class="row rank-row">
                        <span class="r-rank">{{ i + 1 }}</span>
                        <span class="r-main">
                            <component :is="canOpen(AI_PATH) ? 'button' : 'b'" :type="canOpen(AI_PATH) ? 'button' : undefined"
                                class="r-name" :class="{ link: canOpen(AI_PATH) }" @click="canOpen(AI_PATH) && goToStock(w.item)">{{ w.name }}</component>
                            <small class="r-sub r-links">
                                <button v-if="canOpen(AI_PATH)" type="button" @click="goToStock(w.item)">AI 분석</button>
                                <button v-if="canOpen(CHART_PATH)" type="button" @click="goToChart(w.item)">차트</button>
                            </small>
                        </span>
                        <span class="r-val">
                            <b>{{ formatNumber(w.item.close) }}</b>
                            <span class="badge" :class="w.chg.cls">{{ w.pctText }}</span>
                        </span>
                    </li>
                </ol>
                <button v-if="canOpen(BUY_TARGET_PATH)" type="button" class="more" @click="router.push(BUY_TARGET_PATH)">매수추천 전체 보기</button>
            </section>

            <!-- ── 3. 지난달 성과: 큰 숫자 하나 + 상위 종목 리스트(현행 계산 유지) ── -->
            <section v-if="perf && perf.evaluated_count" class="sec perf" aria-labelledby="perf-title">
                <div class="sec-head">
                    <h2 id="perf-title">{{ perfMonthLabel }} 양봉상회 성과</h2>
                </div>
                <p class="sec-sub">표시일 이후 {{ perf.hold_days }}거래일 안 최고가 기준</p>

                <div class="hero">
                    <span class="hero-label">상위 {{ perf.top_pct }}% 평균 · {{ perf.top_count }}종목</span>
                    <b class="hero-big" :class="clsOf(perf.top_avg_return)">{{ pctText(perf.top_avg_return) }}</b>
                    <span class="hero-sub">전체 평균 <b :class="clsOf(perf.avg_return)">{{ pctText(perf.avg_return) }}</b> · {{ perf.evaluated_count }}종목</span>
                </div>

                <ol class="rows perf-rows">
                    <li v-for="(p, i) in perfRows" :key="p.stock_code" class="row rank-row">
                        <component :is="canOpenDetail ? 'button' : 'div'" :type="canOpenDetail ? 'button' : undefined"
                            class="row-hit" :class="{ link: canOpenDetail }" @click="canOpenDetail && goToPerfStock(p)">
                            <span class="r-rank">{{ i + 1 }}</span>
                            <span class="r-main">
                                <b class="r-name">{{ p.stock_name }}</b>
                                <small class="r-sub">{{ mdText(p.ymd) }} {{ formatNumber(p.entry_price) }} → {{ mdText(p.peak_ymd) }} {{ formatNumber(p.peak_price) }}</small>
                            </span>
                            <span class="r-val"><span class="badge" :class="clsOf(p.max_return)">{{ pctText(p.max_return) }}</span></span>
                        </component>
                    </li>
                </ol>
                <p class="foot-note">
                    표시일 종가 대비 이후 {{ perf.hold_days }}거래일 중 가장 높았던 가격 기준이며, 실제로 판 가격과 다를 수 있습니다.
                    같은 종목은 그 달 처음 표시된 1건만 셉니다.
                </p>
                <button v-if="perf.top_list.length > PERF_COUNT" type="button" class="more" :aria-expanded="perfAll ? 'true' : 'false'"
                    @click="perfAll = !perfAll">{{ perfAll ? '접기' : '상위 종목 더 보기' }}</button>
            </section>

            <!-- 광고 1자리: 성과와 공지 사이(AD_FREE·앱 네이티브 광고 환경에서는 비어 있다) -->
            <section v-if="heroAdVisible" class="sec hero-ad" aria-label="광고">
                <AdSlot placement="homeHero" />
            </section>

            <!-- ── 공지사항 ── -->
            <section class="sec notice" aria-labelledby="notice-title">
                <div class="sec-head">
                    <h2 id="notice-title">공지사항</h2>
                </div>
                <p v-if="!notices.length" class="notice-empty">등록된 공지사항이 없습니다.</p>
                <ul v-else class="notice-list">
                    <li v-for="n in notices" :key="n.notice_id">
                        <button type="button" class="notice-row" @click="goToNotice(n)">
                            <span class="notice-title"><span class="notice-cat">{{ n.category }}</span>{{ n.title }}</span>
                            <span class="notice-date">{{ noticeDateText(n.created_date) }}</span>
                        </button>
                    </li>
                </ul>
                <button type="button" class="more" @click="router.push(NOTICE_LIST_PATH)">더 보기</button>
            </section>

            <!-- ── 고지: 연회색 바탕 맨 아래 ── -->
            <footer class="simple-foot">
                <ul class="notes">
                    <li>투자 판단과 그 결과의 책임은 이용자 본인에게 있습니다.</li>
                    <li>주식 투자는 원금 손실이 날 수 있습니다.</li>
                    <li>과거 성과는 앞으로의 수익을 보장하지 않습니다.</li>
                    <li>화면의 시세는 실제보다 몇 분 늦을 수 있습니다.</li>
                </ul>
            </footer>
        </main>
    </div>
</template>

<script setup>
/**
 * 양봉상회 홈(2026-11-15 개편 1차). 순서: 시황 → AI 분석 종목(≤3) → 지난달 성과 → 공지.
 * 데이터는 기존 홈과 같은 API(전부 비로그인 허용)를 쓴다. 알고리즘·계산은 그대로다.
 *   - AI 분석 종목: 종목 이름·등락과 AI 분석·차트 확인 버튼만(근거·살 만한 가격·내 조건 충족은 2026-11-15 뺌).
 *   - 내 설정(보조지표 수치)으로 서버 후보를 다시 걸러 설정한 순서로 보여 준다(indicators.evaluate / persona.orderForType).
 */
import AdSlot from '../common/AdSlot.vue';
import aibeesApi from '@scripts/aibeesApi.js';
import { assUserSession } from '@scripts/stores/user-stores.js';
import { usePersonaStore } from '@scripts/stores/persona-store.js';
import { hasRole, WORKER_ROLE } from '@scripts/useAccess.js';
import { useShowAds } from '@scripts/useAds.js';
import { isNativeAdsEnabled } from '@scripts/useAdMob.js';
import { ONBOARDING_PATH, isGuestPath } from '@scripts/authPaths.js';
import { NOTICE_LIST_PATH, NOTICE_DETAIL_PATH, noticeDateText } from '@scripts/notice.js';
import { numOrNull, formatNumber, changeInfo } from '@scripts/stockSignals.js';
import { orderForType, marketWeather } from '@scripts/persona.js';
import { evaluate, passRuleText } from '@scripts/indicators.js';

const router = useRouter();
const userSession = assUserSession();
const persona = usePersonaStore();

const isLoggedIn = computed(() => !!userSession.user.accessToken);
const userName = computed(() => userSession.getUserInfo || '');
const userInitial = computed(() => (userName.value?.[0] ?? '?').toUpperCase());
const isWorker = computed(() => hasRole(WORKER_ROLE));
const showAds = useShowAds();

// 앱(AdMob)은 네이티브 광고가 화면 위에 겹쳐 그려져 스크롤되는 자리에 못 넣는다 → 하단 배너가 맡는다.
const heroAdVisible = computed(() => !isWorker.value && showAds.value && !isNativeAdsEnabled());

// 종목 상세(/stock/info)는 로그인하고 그 메뉴 권한이 있는 사용자만 연다. 아니면 목록 행을 누를 수 없게 그린다
// (게스트 권한에 공개 메뉴로 들어 있어도 비로그인은 홈·온보딩 밖으로 못 나가므로 누르면 로그인 화면으로 튕긴다).
const canOpenDetail = computed(() => isLoggedIn.value && userSession.access.paths.includes('/stock/info'));

/* ── 계정 메뉴·헤더 ── */
const menuOpen = ref(false);
const accountRef = ref(null);
const onDocClick = (e) => {
    if (menuOpen.value && accountRef.value && !accountRef.value.contains(e.target)) menuOpen.value = false;
};
const onKeyDown = (e) => { if (e.key === 'Escape') menuOpen.value = false; };

const goTo = (path) => { menuOpen.value = false; router.push(path); };

const logout = () => {
    menuOpen.value = false;
    userSession.logoutUser();
    router.push('/login');
};

const scrolled = ref(false);

const onScroll = () => {
    const next = window.scrollY > 8;
    if (next !== scrolled.value) scrolled.value = next;
};

/* ── 공통 표기 ── */
const dirOf = (n) => (n > 0 ? 1 : (n < 0 ? -1 : 0));
const clsOf = (n) => ['down', 'flat', 'up'][dirOf(numOrNull(n) ?? 0) + 1];
const signed = (n, digits) => `${n > 0 ? '+' : (n < 0 ? '−' : '')}${Math.abs(n).toFixed(digits)}`;
const pctText = (v) => {
    const n = numOrNull(v);
    return n === null ? '–' : `${signed(n, 1)}%`;
};
const priceText = (v) => {
    const n = numOrNull(v);
    return n === null ? '–' : n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
};
const mdText = (ymd) => `${Number(String(ymd).slice(4, 6))}/${Number(String(ymd).slice(6, 8))}`;

/* ── 1. 시황 ── (서버 1분 캐시 → 화면도 1분마다) */
const marketData = ref([]);
let marketTimer = null;
const loadMarketSnapshot = async () => {
    try {
        const { data } = await aibeesApi.get('/api/v1/indicators/market-snapshot');
        if (Array.isArray(data?.data) && data.data.length) marketData.value = data.data;
    } catch (e) { /* 보조 정보 — 직전 값 유지 */ }
};
const sparkPoints = (values) => {
    const vs = (values || []).map(numOrNull).filter(v => v !== null);
    if (vs.length < 2) return null;
    const min = Math.min(...vs);
    const span = Math.max(...vs) - min || 1;
    return vs.map((v, i) => `${(i / (vs.length - 1) * 64).toFixed(1)},${(22 - (v - min) / span * 20).toFixed(1)}`).join(' ');
};
const INDEX_LABEL = { kospi: '코스피', kosdaq: '코스닥' };
const indexCards = computed(() => marketData.value.filter(m => m.key !== 'usdkrw').map(m => {
    const r5 = numOrNull(m.rate_5d);
    const r20 = numOrNull(m.rate_20d);
    const r1 = numOrNull(m.rate_1d);
    return {
        key: m.key,
        label: INDEX_LABEL[m.key] ?? m.label ?? m.code,
        priceText: priceText(m.price),
        sparkPoints: sparkPoints(m.spark),
        sparkCls: clsOf(r20),
        todayText: r1 === null ? '' : `${signed(r1, 1)}%`,
        todayCls: clsOf(r1),
        periods: [
            { label: '5일', text: r5 === null ? '–' : `${signed(r5, 1)}%`, cls: clsOf(r5) },
            { label: '20일', text: r20 === null ? '–' : `${signed(r20, 1)}%`, cls: clsOf(r20) },
        ],
    };
}));
const fxItem = computed(() => {
    const m = marketData.value.find(x => x.key === 'usdkrw');
    if (!m) return null;
    const rate = numOrNull(m.rate);
    const change = numOrNull(m.change);
    const dir = dirOf(rate ?? 0);
    const chgPart = change !== null && dir !== 0 ? `${signed(change, 2)} ` : '';  // 예) −4.70 (0.34%)
    return {
        priceText: priceText(m.price),
        chgText: rate === null ? '' : `${chgPart}(${Math.abs(rate).toFixed(2)}%)`,
        cls: clsOf(rate),
    };
});
const weather = computed(() => marketWeather(marketData.value));

/* ── 2. AI 분석 종목 ── (날짜를 보내지 않으면 서버가 가장 최근 표시일을 고른다)
 *   2026-11-15 '시장이 주목하는 회사'(근거·살 만한 가격·내 조건 충족)에서 되돌림: 종목 이름·등락과 AI 분석·차트 확인 버튼만. */
const HOME_COUNT = 3;
const AI_PATH = '/stock/info';
const CHART_PATH = '/stock/chart';
const BUY_TARGET_PATH = '/stock/buy-target';
// 비로그인 공개 경로(authPaths.GUEST_PATHS)거나 서버가 이 사용자에게 허용한 메뉴면 버튼을 보인다.
const canOpen = (path) => isGuestPath(path) || userSession.access.paths.includes(path);

const items = ref([]);
const isLoading = ref(true);
const showAll = ref(false);
const loadItems = async () => {
    isLoading.value = true;
    try {
        const { data } = await aibeesApi.get('/api/v1/stocks/buy-target');
        items.value = Array.isArray(data?.data) ? data.data : [];
    } catch (e) {
        console.error('[home] 주목 종목 조회 실패', e);
        items.value = [];
    } finally {
        isLoading.value = false;
    }
};

const type = computed(() => persona.currentType);
// 서버가 준 후보를 내 설정의 보조지표로 다시 판정해 걸러 낸 뒤, 설정의 순서로 정렬한다.
const passRule = computed(() => passRuleText(type.value.settings));
const ordered = computed(() => {
    const judged = items.value.map(item => ({ item, ev: evaluate(item, type.value.settings) })).filter(x => x.ev.match);
    return orderForType(judged.map(x => x.item), type.value).map(item => ({
        item,
        code: item.stock_code,
        name: item.stock_name,
        chg: changeInfo(item),
    })).map(w => ({
        ...w,
        pctText: w.chg.pct === null ? '–' : `${signed(w.chg.pct, 2)}%`,
        absText: w.chg.abs === null || !w.chg.dir ? '' : `${w.chg.dir > 0 ? '▲' : '▼'}${w.chg.abs.toLocaleString()}`,
    }));
});
const visibleRows = computed(() => (showAll.value ? ordered.value : ordered.value.slice(0, HOME_COUNT)));
const restCount = computed(() => Math.max(0, ordered.value.length - HOME_COUNT));
const basisText = computed(() => {
    const ymd = items.value[0]?.ymd;
    return ymd ? `${mdText(String(ymd).replaceAll('-', ''))} 종가 기준` : '';
});
watch(() => type.value, () => { showAll.value = false; });

const goToStock = (item) => router.push({
    path: AI_PATH,
    query: { stock_code: item.stock_code, stock_name: item.stock_name, ymd: String(item.ymd ?? '').replaceAll('-', '') },
});
const goToChart = (item) => router.push({ path: CHART_PATH, query: { code: item.stock_code } });

/* ── 3. 지난달 성과 ── (서버가 표시일 종가 → 5거래일 내 최고가를 계산, 6시간 캐시) */
const perf = ref(null);
const loadPerformance = async () => {
    try {
        const { data } = await aibeesApi.get('/api/v1/stocks/buy-target/performance');
        perf.value = data?.data ?? null;
    } catch (e) { perf.value = null; }
};
const perfMonthLabel = computed(() => (perf.value ? `${Number(perf.value.ym.slice(4, 6))}월` : ''));
// 성과 리스트: 상위 3종목만 먼저, 나머지는 '더 보기'로 펼친다.
const PERF_COUNT = 3;
const perfAll = ref(false);
const perfRows = computed(() => {
    const list = perf.value?.top_list ?? [];
    return perfAll.value ? list : list.slice(0, PERF_COUNT);
});
const goToPerfStock = (p) => router.push({
    path: '/stock/info',
    query: { stock_code: p.stock_code, stock_name: p.stock_name, ymd: String(p.ymd).replaceAll('-', '') },
});

/* ── 공지 ── */
const notices = ref([]);
const loadNotices = async () => {
    try {
        const { data } = await aibeesApi.get('/api/v1/notices', { params: { page: 0, size: 3 } });
        notices.value = Array.isArray(data?.data) ? data.data : [];
    } catch (e) {
        notices.value = [];
    }
};

const goToNotice = (n) => router.push({ path: NOTICE_DETAIL_PATH, query: { id: n.notice_id, from: 'home' } });

onMounted(() => {
    document.addEventListener('click', onDocClick, true);
    document.addEventListener('keydown', onKeyDown);
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
    loadMarketSnapshot();
    marketTimer = setInterval(loadMarketSnapshot, 60 * 1000);
    loadItems();
    loadPerformance();
    loadNotices();
});

onBeforeUnmount(() => {
    clearInterval(marketTimer);
    document.removeEventListener('click', onDocClick, true);
    document.removeEventListener('keydown', onKeyDown);
    window.removeEventListener('scroll', onScroll);
});
</script>

<style scoped lang="scss">
@use '@@/_home-tokens.scss' as *;

/* 2026-11-17 화이트 톤 개편: 섹션 = 흰 판, 섹션 사이 = 연회색 띠($band-h). 섹션 안은 선 없이 여백으로 나눈다.
 * 글자 위계 — 섹션 제목 20 / 항목 16 / 보조 13(회색) / 부가 12(연회색). 색은 등락에만. */
#home-simple {
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

/* ── 헤더 ── */
.home-header {
    background: $bar;
    position: sticky;
    top: env(safe-area-inset-top, 0px);
    z-index: 50;
    transition: box-shadow .15s ease;
}
.home-header.scrolled { box-shadow: 0 1px 0 $line; }
.hh-row {
    max-width: 640px;
    margin: 0 auto;
    height: 56px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 8px 0 $pad-x;
}
.brand {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    min-height: 44px;
    padding: 0;
    border: 0;
    background: transparent;
    cursor: pointer;
    .brand-logo { width: 26px; height: 26px; }
    .brand-name { font-family: $font-brand; font-size: 19px; font-weight: 700; color: $ink; letter-spacing: -0.4px; }
}
.hh-actions { display: flex; align-items: center; gap: 2px; }
.guide-btn {
    height: 32px;
    margin-right: 4px;
    padding: 0 12px;
    border: 1px solid $line;
    border-radius: 8px;
    background: transparent;
    color: $sub-ink;
    font-size: 13px;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    cursor: pointer;
    .dot { width: 6px; height: 6px; border-radius: 3px; background: $honey-500; }
}
.icon-btn {
    width: 44px;
    height: 44px;
    border: 0;
    background: transparent;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
}
.avatar {
    width: 30px;
    height: 30px;
    border-radius: 15px;
    background: $band;
    color: $ink;
    font-weight: 700;
    font-size: 13px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
}
.login-btn {
    min-height: 44px;
    padding: 0 12px;
    border: 0;
    background: transparent;
    color: $ink;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
}
.account { position: relative; }
.account-menu {
    position: absolute;
    right: 0;
    top: 46px;
    z-index: 60;
    min-width: 160px;
    margin: 0;
    padding: 6px;
    list-style: none;
    background: $card;
    border: 1px solid $line;
    border-radius: 12px;
    box-shadow: 0 8px 24px rgba(0, 0, 0, .08);
    .am-name { padding: 8px 10px 6px; font-size: 12px; color: $sub; }
    button {
        width: 100%;
        min-height: 44px;
        padding: 0 10px;
        border: 0;
        border-radius: 8px;
        background: transparent;
        text-align: left;
        font-size: 14px;
        color: $ink;
        cursor: pointer;
        &:hover { background: $bg; }
        &.danger { color: $up; }
    }
}

/* ── 본문: 흰 판을 띠 간격으로 쌓는다 ── */
.home-main {
    max-width: 640px;
    margin: 0 auto;
    display: flex;
    flex-direction: column;
    gap: $band-h;
}
.sec {
    background: $card;
    padding: 28px $pad-x 8px;
}
.sec-head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 8px;
    h2 { margin: 0; font-size: 20px; font-weight: 700; letter-spacing: -0.5px; }
    .meta { font-size: 13px; color: $sub; white-space: nowrap; }
}
.sec-sub { margin: 6px 0 0; font-size: 13px; color: $sub; }
.meta-link {
    min-height: 32px;
    padding: 0;
    border: 0;
    background: transparent;
    color: $sub;
    font-size: 13px;
    cursor: pointer;
    &::after { content: ' ›'; color: $sub-2; }
}
.text-link {
    min-height: 32px;
    padding: 0 2px;
    border: 0;
    background: transparent;
    color: $sub-ink;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    text-decoration: underline;
    text-underline-offset: 3px;
}
// 섹션 끝 "더 보기": 얇은 선 한 줄 + 가운데 회색 글자
.more {
    display: flex;
    align-items: center;
    justify-content: center;
    width: calc(100% + #{$pad-x * 2});
    height: 52px;
    margin: 8px (-$pad-x) 0;
    border: 0;
    border-top: 1px solid $line;
    background: transparent;
    color: $sub-ink;
    font-size: 15px;
    cursor: pointer;
    &::after { content: '›'; margin-left: 6px; color: $sub-2; font-size: 17px; }
    &[aria-expanded="true"]::after { content: ''; margin: 0; }
    @media (hover: hover) { &:hover { background: $bg; } }
}

.up   { color: $up; }
.down { color: $down; }
.flat { color: $sub; }

/* ── 공통 리스트 행 ── */
.rows { margin: 8px 0 0; padding: 0; list-style: none; }
.row {
    display: flex;
    align-items: center;
    min-height: 64px;
    gap: 0;
}
.row-hit {
    display: flex;
    align-items: center;
    width: 100%;
    min-height: 64px;
    padding: 0;
    border: 0;
    background: transparent;
    color: inherit;
    text-align: left;
    &.link { cursor: pointer; }
}
.r-rank { width: 28px; flex-shrink: 0; font-size: 17px; font-weight: 700; color: $amber-700; }
.r-main { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 3px; }
.r-name {
    display: block;
    padding: 0;
    border: 0;
    background: transparent;
    color: $ink;
    text-align: left;
    font-size: 16px;
    font-weight: 600;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    &.link { cursor: pointer; }
}
.r-sub {
    font-size: 13px;
    color: $sub;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    i { font-style: normal; }
}
.r-links {
    display: flex;
    gap: 0;
    button {
        min-height: 24px;
        padding: 0;
        border: 0;
        background: transparent;
        color: $sub;
        font-size: 13px;
        cursor: pointer;
        & + button::before { content: '·'; margin: 0 6px; color: $sub-2; }
    }
}
.r-spark { width: 56px; height: 24px; flex: none; margin: 0 16px 0 8px; }
.r-val {
    flex-shrink: 0;
    margin-left: 12px;
    text-align: right;
    display: flex;
    flex-direction: column;
    gap: 3px;
    b { font-size: 16px; font-weight: 600; color: $ink; &.up { color: $up; } &.down { color: $down; } }
    small { font-size: 13px; font-weight: 500; color: $sub; &.up { color: $up; } &.down { color: $down; } }
}

/* ── 1. 시황 ── */
.weather {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-top: 14px;
    .wx-box {
        width: 44px;
        height: 44px;
        flex: none;
        border-radius: 12px;
        background: $bg;
        display: flex;
        align-items: center;
        justify-content: center;
        color: $sub-ink;
    }
    .wx-icon { width: 28px; height: 28px; }
    .wx-text { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
    .wx-name { font-size: 13px; color: $sub; }
    .wx-desc { font-size: 18px; font-weight: 700; letter-spacing: -0.4px; color: $ink; }
}

/* ── 2. TOP 3 ── */
.w-empty { padding: 20px 0 12px; font-size: 14px; color: $sub; text-align: center; p { margin: 0 0 6px; } }
.w-skeleton {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 12px 0;
    i { display: block; height: 44px; border-radius: 8px; background: $bg; animation: pulse 1.6s infinite ease-in-out; }
}
@keyframes pulse { 50% { opacity: .55; } }
@media (prefers-reduced-motion: reduce) { .w-skeleton i { animation: none; } }

/* ── 3. 성과 ── */
.hero {
    display: flex;
    flex-direction: column;
    margin: 18px 0 6px;
    .hero-label { font-size: 14px; color: $sub-ink; }
    .hero-big { font-size: 34px; font-weight: 700; letter-spacing: -1px; line-height: 1.25; color: $ink; &.up { color: $up; } &.down { color: $down; } }
    .hero-sub { margin-top: 4px; font-size: 14px; color: $sub; b { font-weight: 600; } }
}
.perf-rows { margin-top: 16px; padding-top: 4px; border-top: 1px solid $line; }
.foot-note { margin: 6px 0 16px; font-size: 12px; line-height: 1.55; color: $sub-2; word-break: keep-all; }

.hero-ad { padding: 12px $pad-x; }

/* ── 공지 ── */
.notice { padding-bottom: 12px; }
.notice-empty { margin: 0; padding: 16px 0; font-size: 13px; color: $sub; }
.notice-list { margin: 8px 0 0; padding: 0; list-style: none; }
.notice-row {
    width: 100%;
    display: flex;
    flex-direction: column;
    align-items: stretch;
    gap: 4px;
    padding: 14px 0 !important;
    border-bottom: 1px solid $line !important;
    min-height: 52px;
    padding: 0;
    border: 0;
    background: transparent;
    color: $ink;
    text-align: left;
    cursor: pointer;
    .notice-cat { flex-shrink: 0; width: 56px; font-size: 13px; color: $sub; }
    .notice-title { flex: 1; min-width: 0; font-size: 15px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .notice-date { flex-shrink: 0; margin-left: 12px; font-size: 13px; color: $sub-2; }
}

/* ── 고지: 띠 색 바탕 위 연회색 작은 글자 ── */
.simple-foot {
    padding: 12px $pad-x 28px;
    .notes {
        margin: 0;
        padding: 0;
        list-style: none;
        font-size: 12px;
        line-height: 1.6;
        color: $sub-2;
    }
}

/* ── 2026-11-17 꿀빛 톤(한국투자 참고): 크림 카드 · 앰버 순위 · 등락 배지. 모서리는 $radius(12px) ── */
.badge {
    display: inline-flex;
    align-items: center;
    height: 22px;
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
.row { min-height: 68px; }
.r-val { gap: 4px; align-items: flex-end; }
.hero {
    margin: 16px 0 4px;
    padding: 18px;
    border-radius: $radius;
    background: $honey-50;
}
.perf-rows { margin-top: 8px; padding-top: 0; border-top: 0; }
.notice-list li:last-child .notice-row { border-bottom: 0 !important; }
.notice-row {
    .notice-title { font-size: 15px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .notice-cat { width: auto; margin-right: 6px; font-size: 15px; font-weight: 600; color: $amber-700; }
    .notice-date { margin-left: 0; font-size: 13px; color: $sub; }
}
.notice { padding-bottom: 8px; }
.simple-foot .notes { color: $sub; }
</style>
