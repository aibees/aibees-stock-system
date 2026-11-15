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
                    <button type="button" class="guide-btn" @click="router.push(ONBOARDING_PATH)">처음이세요?</button>
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
            <div class="header-edge" aria-hidden="true"></div>
        </header>

        <main class="home-main">

            <!-- ── 1. 시황: 한 줄 요약 + 코스피/코스닥 + 원/달러 ── -->
            <section class="market" aria-labelledby="market-title">
                <h2 id="market-title" class="sec-title">오늘 시장</h2>
                <div v-if="weather" class="weather" :class="weather.key" role="status">
                    <svg class="wx-icon" viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
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
                            <path d="M25 30l-5 8h6l-4 8" stroke-width="2.6"></path>
                        </template>
                    </svg>
                    <div class="wx-text">
                        <b class="wx-name">{{ weather.text }}</b>
                        <span class="wx-desc">{{ weather.desc }}</span>
                        <span class="wx-basis">오늘 코스피 <i :class="clsOf(weather.kospi)">{{ pctText(weather.kospi) }}</i> · 코스닥 <i :class="clsOf(weather.kosdaq)">{{ pctText(weather.kosdaq) }}</i></span>
                    </div>
                </div>
                <div class="mk-cards">
                    <article v-for="m in indexCards" :key="m.key" class="mk-card">
                        <div class="mk-top">
                            <span class="mk-code">{{ m.label }}</span>
                            <svg v-if="m.sparkPoints" class="mk-spark" :class="m.sparkCls" viewBox="0 0 64 24" preserveAspectRatio="none" aria-hidden="true">
                                <polyline :points="m.sparkPoints" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke" />
                            </svg>
                        </div>
                        <div class="mk-price">{{ m.priceText }}</div>
                        <div class="mk-rates">
                            <span v-for="p in m.periods" :key="p.label" class="mk-rate">
                                {{ p.label }} <b :class="p.cls">{{ p.text }}</b>
                            </span>
                        </div>
                    </article>
                </div>
                <div v-if="fxItem" class="mk-fx">
                    <span class="mk-fx-label">원/달러</span>
                    <b class="mk-fx-price">{{ fxItem.priceText }}</b>
                    <span class="mk-fx-chg" :class="fxItem.cls">{{ fxItem.chgText }}</span>
                </div>
            </section>

            <!-- ── 2. 시장이 주목하는 회사: 내 성향 순서로 3개 + 나머지는 펼쳐 보기 ── -->
            <section class="watch" aria-labelledby="watch-title">
                <div class="list-head">
                    <h2 id="watch-title">시장이 주목하는 회사</h2>
                    <span v-if="basisText" class="basis">{{ basisText }}</span>
                </div>
                <p class="persona-line">
                    내 성향 <b>{{ type.name }}</b>
                    <button type="button" class="text-link" @click="router.push({ path: ONBOARDING_PATH, query: { pick: '1' } })">바꾸기</button>
                </p>

                <div v-if="isLoading" class="w-skeleton" aria-busy="true" aria-label="불러오는 중">
                    <i v-for="n in 3" :key="n"></i>
                </div>
                <p v-else-if="!ordered.length" class="w-empty">오늘은 조건에 맞는 종목이 없습니다.</p>
                <template v-else>
                    <ol class="w-list">
                        <li v-for="(w, i) in visibleRows" :key="w.code" class="w-item">
                            <component :is="canOpenDetail ? 'button' : 'div'" :type="canOpenDetail ? 'button' : undefined"
                                class="w-row" :class="{ link: canOpenDetail }" @click="canOpenDetail && goToStock(w.item)">
                                <span class="w-name-line">
                                    <span class="rank">{{ String(i + 1).padStart(2, '0') }}</span>
                                    <span class="name">{{ w.name }}</span>
                                    <span class="chg" :class="w.chg.cls">{{ w.chg.text }}</span>
                                </span>
                                <span class="w-reasons">
                                    <span v-for="(r, ri) in w.reasons" :key="ri" class="w-reason"><i aria-hidden="true">✓</i>{{ r }}</span>
                                </span>
                                <span class="w-prices">
                                    <span class="w-price">
                                        <span class="w-label">살 만한 가격</span>
                                        <b>{{ w.buyText }}</b>
                                    </span>
                                    <span class="w-price">
                                        <span class="w-label">정리할 가격 <em>−{{ type.stopPct }}%</em></span>
                                        <b>{{ w.stopText }}</b>
                                    </span>
                                </span>
                            </component>
                        </li>
                    </ol>
                    <button v-if="restCount > 0" type="button" class="more-btn" :aria-expanded="showAll ? 'true' : 'false'"
                        @click="showAll = !showAll">
                        {{ showAll ? '접기' : `전체 보기 · ${restCount}개 더` }}
                    </button>
                    <p class="w-note">
                        살 만한 가격은 표시일 종가입니다. 정리할 가격은 그보다 {{ type.stopPct }}% 낮은 가격으로,
                        여기까지 내려가면 정리를 생각해 볼 기준입니다.
                    </p>
                </template>
            </section>

            <!-- 광고 1자리: 주목 종목과 성과 사이(AD_FREE·앱 네이티브 광고 환경에서는 비어 있다) -->
            <section v-if="heroAdVisible" class="hero-ad" aria-label="광고">
                <AdSlot placement="homeHero" />
            </section>

            <!-- ── 3. 지난달 성과(현행 계산 유지, 표시만 쉬운 말로) ── -->
            <section v-if="perf && perf.evaluated_count" class="perf" aria-labelledby="perf-title">
                <div class="list-head">
                    <h2 id="perf-title">{{ perfMonthLabel }} 양봉상회 성과</h2>
                </div>
                <p class="perf-basis">표시일 이후 {{ perf.hold_days }}거래일 내 최고가 기준</p>

                <ul ref="perfTrack" class="perf-track" aria-label="성과 카드 — 옆으로 넘겨 보세요" @scroll.passive="onPerfScroll">
                    <li class="perf-card summary">
                        <span class="pc-label">상위 {{ perf.top_pct }}% 평균 · {{ perf.top_count }}종목</span>
                        <b class="pc-big" :class="clsOf(perf.top_avg_return)">{{ pctText(perf.top_avg_return) }}</b>
                        <span class="pc-label second">전체 평균 · {{ perf.evaluated_count }}종목</span>
                        <b class="pc-mid" :class="clsOf(perf.avg_return)">{{ pctText(perf.avg_return) }}</b>
                    </li>
                    <li v-for="(p, i) in perf.top_list" :key="p.stock_code" class="perf-card">
                        <component :is="canOpenDetail ? 'button' : 'div'" :type="canOpenDetail ? 'button' : undefined"
                            class="pc-body" :class="{ link: canOpenDetail }" @click="canOpenDetail && goToPerfStock(p)">
                            <span class="pc-name-line">
                                <span class="rank">{{ String(i + 1).padStart(2, '0') }}</span>
                                <span class="name">{{ p.stock_name }}</span>
                            </span>
                            <b class="pc-big" :class="clsOf(p.max_return)">{{ pctText(p.max_return) }}</b>
                            <span class="pc-meta pair">
                                <span>
                                    {{ mdText(p.ymd) }} {{ formatNumber(p.entry_price) }}
                                </span>
                                <span>
                                     → 
                                </span>
                                <span class="to">
                                    <b class="up">
                                        {{ mdText(p.peak_ymd) }} {{ formatNumber(p.peak_price) }}
                                    </b>
                                </span>
                            </span>
                        </component>
                    </li>
                </ul>
                <div class="perf-dots" aria-hidden="true">
                    <i v-for="n in perf.top_list.length + 1" :key="n" :class="{ on: n - 1 === perfIdx }"></i>
                </div>
                <p class="perf-note">
                    표시일 종가 대비 이후 {{ perf.hold_days }}거래일 중 가장 높았던 가격 기준이며, 실제로 판 가격과 다를 수 있습니다.
                    같은 종목은 그 달 처음 표시된 1건만 셉니다.
                </p>
            </section>

            <!-- ── 공지사항 ── -->
            <section class="notice" aria-labelledby="notice-title">
                <div class="list-head">
                    <h2 id="notice-title">공지사항</h2>
                    <button type="button" class="text-link" @click="router.push(NOTICE_LIST_PATH)">전체 보기</button>
                </div>
                <p v-if="!notices.length" class="notice-empty">등록된 공지사항이 없습니다.</p>
                <ul v-else class="notice-list">
                    <li v-for="n in notices" :key="n.notice_id">
                        <button type="button" class="notice-row" @click="goToNotice(n)">
                            <span class="notice-cat" :class="noticeCategoryClass(n.category)">{{ n.category }}</span>
                            <span class="notice-title">{{ n.title }}</span>
                            <span class="notice-date">{{ noticeDateText(n.created_date).slice(5) }}</span>
                        </button>
                    </li>
                </ul>
            </section>

            <!-- ── 고지 ── -->
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
 * 간편 모드 홈(2026-11-15 개편 1차). 순서: 시황 → 시장이 주목하는 회사(≤3) → 지난달 성과 → 공지.
 * 데이터는 기존 홈과 같은 API(전부 비로그인 허용)를 쓴다. 알고리즘·계산은 그대로, 보여 주는 말만 바꾼다.
 *   - '추천' 대신 '시장이 주목하는 회사'. 지표 이름 대신 쉬운 말(persona.reasonLines — 항목마다 한 줄).
 *   - 성향은 목록을 거르지 않고 순서와 정리할 가격만 바꾼다(persona.orderForType / stopPrice).
 * 날짜 이동·정렬·조건 목록·차트·최우선 타겟은 전문가 모드(Home.vue)에만 있다.
 */
import AdSlot from '../common/AdSlot.vue';
import { MOCK_ENABLED } from '@scripts/mock/mockApi.js';
import aibeesApi from '@scripts/aibeesApi.js';
import { assUserSession } from '@scripts/stores/user-stores.js';
import { usePersonaStore } from '@scripts/stores/persona-store.js';
import { hasRole, WORKER_ROLE } from '@scripts/useAccess.js';
import { useShowAds } from '@scripts/useAds.js';
import { isNativeAdsEnabled } from '@scripts/useAdMob.js';
import { ONBOARDING_PATH } from '@scripts/authPaths.js';
import { NOTICE_LIST_PATH, NOTICE_DETAIL_PATH, noticeDateText, noticeCategoryClass } from '@scripts/notice.js';
import { numOrNull, formatNumber, changeInfo } from '@scripts/stockSignals.js';
import { orderForType, stopPrice, reasonLines, marketWeather } from '@scripts/persona.js';

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
const wonText = (v) => (numOrNull(v) === null ? '–' : `${formatNumber(v)}원`);

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
    return {
        key: m.key,
        label: INDEX_LABEL[m.key] ?? m.label ?? m.code,
        priceText: priceText(m.price),
        sparkPoints: sparkPoints(m.spark),
        sparkCls: clsOf(r20),
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
    const mark = dir > 0 ? '▲' : (dir < 0 ? '▼' : '–');
    return {
        priceText: priceText(m.price),
        chgText: rate === null ? '' : `${mark}${change !== null && dir !== 0 ? ` ${Math.abs(change).toFixed(2)}` : ''} ${signed(rate, 2)}%`,
        cls: clsOf(rate),
    };
});
const weather = computed(() => marketWeather(marketData.value));

/* ── 2. 시장이 주목하는 종목 ── (날짜를 보내지 않으면 서버가 가장 최근 표시일을 고른다) */
const HOME_COUNT = 3;
// 목업 미리보기(?reasons=all): 이유를 2줄로 자르지 않고 전부 보여 준다. 평소에는 2줄.
const REASON_MAX = (MOCK_ENABLED && new URLSearchParams(location.search).get('reasons') === 'all') ? 99 : 2;
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
const ordered = computed(() => orderForType(items.value, type.value).map(item => ({
    item,
    code: item.stock_code,
    name: item.stock_name,
    chg: changeInfo(item),
    reasons: reasonLines(item, REASON_MAX),
    buyText: wonText(item.close),
    stopText: wonText(stopPrice(item.close, type.value.stopPct)),
})));
const visibleRows = computed(() => (showAll.value ? ordered.value : ordered.value.slice(0, HOME_COUNT)));
const restCount = computed(() => Math.max(0, ordered.value.length - HOME_COUNT));
const basisText = computed(() => {
    const ymd = items.value[0]?.ymd;
    return ymd ? `${mdText(String(ymd).replaceAll('-', ''))} 종가 기준` : '';
});
watch(() => type.value.key, () => { showAll.value = false; });

const goToStock = (item) => router.push({
    path: '/stock/info',
    query: { stock_code: item.stock_code, stock_name: item.stock_name, ymd: String(item.ymd ?? '').replaceAll('-', '') },
});

/* ── 3. 지난달 성과 ── (서버가 표시일 종가 → 5거래일 내 최고가를 계산, 6시간 캐시) */
const perf = ref(null);
const loadPerformance = async () => {
    try {
        const { data } = await aibeesApi.get('/api/v1/stocks/buy-target/performance');
        perf.value = data?.data ?? null;
    } catch (e) { perf.value = null; }
};
const perfMonthLabel = computed(() => (perf.value ? `${Number(perf.value.ym.slice(4, 6))}월` : ''));
// 캐러셀: 스크롤 위치로 지금 보이는 카드(점 표시)를 구한다.
const perfTrack = ref(null);
const perfIdx = ref(0);
const onPerfScroll = () => {
    const el = perfTrack.value;
    if (!el || !el.children.length) return;
    const step = el.children[1] ? el.children[1].offsetLeft - el.children[0].offsetLeft : el.clientWidth;
    perfIdx.value = Math.min(el.children.length - 1, Math.max(0, Math.round(el.scrollLeft / (step || 1))));
};
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
    } catch (e) { notices.value = []; }
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

#home-simple {
    min-height: 100vh;
    background: $card;
    color: $ink;
    text-align: left;
    font-family: $font-body;
    font-variant-numeric: tabular-nums;
}

/* ── 헤더 (전문가 홈과 같은 모양) ── */
.home-header {
    background: $bar;
    position: sticky;
    top: env(safe-area-inset-top, 0px);
    z-index: 50;
}
.hh-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 2px 8px 6px 16px;
}
.brand {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    min-height: 44px;
    padding: 0;
    border: 0;
    background: transparent;
    cursor: pointer;
    .brand-logo { width: 28px; height: 28px; }
    .brand-name { font-family: $font-brand; font-size: 22px; color: $brown-ink; letter-spacing: .3px; }
}
.hh-actions { display: flex; align-items: center; gap: 2px; }
.guide-btn {
    min-height: 44px;
    padding: 0 8px;
    border: 0;
    background: transparent;
    color: $brown;
    font: inherit;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
}
.icon-btn {
    width: 44px;
    height: 44px;
    border: 0;
    background: transparent;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    color: $brown-ink;
    cursor: pointer;
}
.avatar {
    width: 30px;
    height: 30px;
    border-radius: 15px;
    background: #F6E3A8;
    color: $brown-ink;
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
    color: $brown-ink;
    font: inherit;
    font-size: 14px;
    font-weight: 700;
    cursor: pointer;
}
.header-edge { position: relative; height: 0; }
.header-edge::after {
    content: '';
    position: absolute;
    left: 0;
    right: 0;
    top: 0;
    height: 8px;
    background: radial-gradient(circle at 50% 0, #{$bar} 6.5px, transparent 7px) repeat-x;
    background-size: 16px 8px;
    transition: opacity .15s ease;
}
.home-header.scrolled {
    .header-edge::after { opacity: 0; }
    .hh-row { box-shadow: 0 1px 0 $line-2; }
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
    border: 1px solid $line-2;
    border-radius: 12px;
    box-shadow: 0 10px 24px rgba(74, 40, 20, .16);
    .am-name { padding: 8px 10px 6px; font-size: 12px; color: $sub; }
    button {
        width: 100%;
        min-height: 44px;
        padding: 0 10px;
        border: 0;
        border-radius: 8px;
        background: transparent;
        text-align: left;
        font: inherit;
        font-size: 14px;
        color: $ink;
        cursor: pointer;
        &:hover { background: $bg; }
        &.danger { color: $up; }
    }
}

/* ── 본문: 블록 사이는 옅은 선 한 줄 ── */
.home-main {
    max-width: 640px;
    margin: 0 auto;
    padding: 14px 16px 24px;
    display: flex;
    flex-direction: column;
    gap: 16px;

    > .watch, > .hero-ad, > .perf, > .notice, > .simple-foot {
        margin-top: 4px;
        padding-top: 20px;
        border-top: 1px solid $line-soft;
    }
}

.list-head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 8px;
    margin-bottom: 6px;
    h2 { margin: 0; font-size: 18px; font-weight: 700; }
    .basis { font-size: 12px; color: $sub; white-space: nowrap; }
}
.sec-title { margin: 0; font-size: 18px; font-weight: 700; }
.text-link {
    min-height: 32px;
    padding: 0 2px;
    border: 0;
    background: transparent;
    color: $accent;
    font: inherit;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    text-decoration: underline;
    text-underline-offset: 3px;
}

.up   { color: $up; }
.down { color: $down; }
.flat { color: $sub; }

/* ── 1. 시황 ── */
.market { display: flex; flex-direction: column; gap: 8px; }
.weather {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 6px 2px 10px;
    .wx-icon { width: 52px; height: 52px; flex: none; }
    .wx-text { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
    .wx-name { font-size: 24px; font-weight: 800; letter-spacing: -.4px; line-height: 1.15; }
    .wx-desc { font-size: 14px; color: $ink; }
    .wx-basis { font-size: 12px; color: $sub; i { font-style: normal; font-weight: 600; } }
    &.sunny .wx-icon { color: #E8960C; }
    &.warm  .wx-icon { color: #D9892B; }
    &.cloudy .wx-icon { color: #6E7F99; }
    &.storm .wx-icon { color: #3A4C8A; }
    &.sunny .wx-name { color: #C47A00; }
    &.warm  .wx-name { color: #B8691A; }
    &.cloudy .wx-name { color: #55667F; }
    &.storm .wx-name { color: #2B3A78; }
}
.mk-cards { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
.mk-card {
    min-width: 0;
    padding: 12px 12px 10px;
    background: $card;
    border: 1px solid $line;
    border-radius: 12px;
    display: flex;
    flex-direction: column;
    gap: 4px;
}
.mk-top { display: flex; align-items: center; justify-content: space-between; gap: 6px; }
.mk-code { font-size: 13px; font-weight: 600; color: $sub; }
.mk-spark { width: 64px; height: 24px; flex: none; }
.mk-price { font-size: 22px; font-weight: 700; color: $ink; letter-spacing: -.3px; }
.mk-rates { display: flex; flex-wrap: wrap; column-gap: 12px; row-gap: 2px; }
.mk-rate {
    font-size: 11px;
    color: $sub;
    white-space: nowrap;
    b { margin-left: 2px; font-size: 13px; font-weight: 600; }
}
.mk-fx {
    display: flex;
    align-items: baseline;
    gap: 8px;
    padding: 0 4px;
    font-size: 12px;
    color: $sub;
    .mk-fx-price { font-size: 14px; color: $ink; }
    .mk-fx-chg { font-weight: 600; }
}

/* ── 2. 주목 종목 ── */
.persona-line {
    margin: 0 0 10px;
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 13px;
    color: $sub;
    b { color: $ink; font-weight: 700; }
}
.w-list { margin: 0; padding: 0; list-style: none; border-top: 1px solid $line; }
.w-item { border-bottom: 1px solid $line; }
.w-row {
    width: 100%;
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding: 14px 0;
    border: 0;
    background: transparent;
    color: $ink;
    text-align: left;
    font: inherit;
    &.link { cursor: pointer; }
    &.link:active { background: $bg; }
}
.w-name-line {
    display: flex;
    align-items: baseline;
    gap: 6px;
    min-width: 0;
    .rank { font-family: $font-brand; font-size: 20px; line-height: 1; color: $accent; flex-shrink: 0; }
    .name { font-size: 17px; font-weight: 700; min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .chg { margin-left: auto; flex-shrink: 0; font-size: 13px; font-weight: 600; white-space: nowrap; }
}
.w-reasons { display: flex; flex-direction: column; gap: 3px; }
.w-reason {
    display: flex;
    gap: 6px;
    font-size: 14px;
    line-height: 1.4;
    color: $ink;
    i { font-style: normal; font-weight: 700; color: $accent; flex: none; }
}
.w-prices {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    margin-top: 4px;
    padding-top: 10px;
    border-top: 1px solid $line-soft;
}
.w-price {
    display: flex;
    flex-direction: column;
    gap: 2px;
    & + & { padding-left: 16px; border-left: 1px solid $line-soft; }
    .w-label { font-size: 12px; color: $sub-2; em { font-style: normal; color: $down; font-weight: 600; margin-left: 2px; } }
    b { font-size: 17px; font-weight: 700; color: $ink; }
}
.more-btn {
    width: 100%;
    min-height: 44px;
    margin-top: 4px;
    border: 0;
    background: transparent;
    color: $brown;
    font: inherit;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    @media (hover: hover) { &:hover { background: $bg; } }
}
.w-note { margin: 8px 0 0; font-size: 12px; line-height: 1.6; color: $sub-2; word-break: keep-all; }
.w-empty { margin: 0; padding: 20px 0; font-size: 14px; color: $sub; text-align: center; border-top: 1px solid $line; }
.w-skeleton {
    display: flex;
    flex-direction: column;
    gap: 10px;
    i { display: block; height: 84px; border-radius: 10px; background: $bg; animation: pulse 1.6s infinite ease-in-out; }
}
@keyframes pulse { 50% { opacity: .55; } }
@media (prefers-reduced-motion: reduce) { .w-skeleton i { animation: none; } }

.hero-ad { display: block; }

/* ── 3. 지난달 성과 ── */
.perf-basis { margin: 0 0 8px; font-size: 12px; color: $sub; }
.perf-track {
    list-style: none;
    margin: 0 -16px;
    padding: 4px 16px 4px;
    display: flex;
    gap: 8px;
    overflow-x: auto;
    scroll-snap-type: x mandatory;
    scroll-padding-left: 16px;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: none;
    &::-webkit-scrollbar { display: none; }
}
.perf-card {
    flex: 0 0 176px;
    scroll-snap-align: start;
    box-sizing: border-box;
    border: 1px solid $line;
    border-radius: 12px;
    background: $card;
    display: flex;
    flex-direction: column;
    gap: 2px;
    padding: 10px 12px;
    &.summary { background: $bg; justify-content: center; }
}
.pc-body {
    display: flex; flex-direction: column; gap: 3px; width: 100%; padding: 0;
    border: 0; background: transparent; color: inherit; text-align: left; font: inherit;
    &.link { cursor: pointer; }
}
.pc-name-line {
    display: flex; align-items: baseline; gap: 6px; min-width: 0;
    .rank { font-family: $font-brand; font-size: 15px; line-height: 1; color: $accent; flex-shrink: 0; }
    .name { font-size: 14px; font-weight: 700; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
}
.pc-big { font-size: 20px; font-weight: 800; letter-spacing: -.3px; color: $ink; margin: 1px 0; }
.pc-mid { font-size: 16px; font-weight: 700; letter-spacing: -.3px; color: $ink; }
.pc-big.up, .pc-mid.up { color: $up; }
.pc-big.down, .pc-mid.down { color: $down; }
.pc-label { font-size: 11px; color: $sub; &.second { margin-top: 6px; } }
.pc-sub, .pc-meta { font-size: 11px; color: $sub-2; white-space: nowrap; b { font-weight: 800; }
    // 시작가는 왼쪽, 최고가는 오른쪽 끝에 붙여 카드 폭을 꽉 채운다
    &.pair { display: flex; justify-content: space-between; gap: 6px; } }
.perf-dots {
    display: flex; justify-content: center; gap: 6px; margin-top: 8px;
    i { width: 6px; height: 6px; border-radius: 50%; background: $line-2; transition: background .15s; }
    i.on { background: $accent; }
}
.perf-note { margin: 8px 0 0; font-size: 11px; line-height: 1.5; color: $sub-2; }

/* ── 공지(작게) ── */
.notice-empty { margin: 0; padding: 14px 0; font-size: 13px; color: $sub; border-top: 1px solid $line; }
.notice-list { border-top: 1px solid $line; }
.notice-list { margin: 0; padding: 0; list-style: none; }
.notice-row {
    width: 100%;
    display: flex;
    align-items: baseline;
    gap: 8px;
    padding: 9px 0;
    border: 0;
    border-bottom: 1px solid $line;
    background: transparent;
    color: $ink;
    text-align: left;
    font: inherit;
    cursor: pointer;
    .notice-cat { flex-shrink: 0; font-size: 12px; font-weight: 600; color: $accent; &.cat-maint { color: $up; } &.cat-update { color: $down; } }
    .notice-title { flex: 1; min-width: 0; font-size: 14px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .notice-date { flex-shrink: 0; font-size: 12px; color: $sub-2; }
}

/* ── 고지 ── */
.simple-foot {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 10px;
    .notes {
        margin: 0;
        padding: 0;
        list-style: none;
        font-size: 11px;
        line-height: 1.6;
        color: $sub-2;
        text-align: center;
    }
}
</style>
