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
                    <button type="button" class="guide-btn" @click="router.push(INTRO_PATH)"><i class="dot" aria-hidden="true"></i>처음이세요?</button>
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
                    <!-- 날씨 그림: 이모지 스타일 3D 그림(Microsoft Fluent Emoji, MIT — public/img/weather/LICENSE-fluentui-emoji.txt) -->
                    <span class="wx-box" aria-hidden="true">
                        <img class="wx-img" :src="`/img/weather/${weather.key}.png`" alt="" width="36" height="36" />
                    </span>
                    <span class="wx-text">
                        <span class="wx-name">{{ weather.text }}</span>
                        <b class="wx-desc">{{ weather.desc }}</b>
                    </span>
                </div>
                <!-- 달러 금리·코스피·코스닥·원/달러: 옆으로 넘기는 카드(이름 · 값 · 오늘 등락 · 흐름 차트). 2026-11-22 -->
                <ul class="mkt-tiles" aria-label="오늘 시장 지표">
                    <li v-for="t in marketTiles" :key="t.key" class="mkt-tile" :class="t.cls">
                        <span class="mt-name">{{ t.label }}</span>
                        <b class="mt-price">{{ t.priceText }}</b>
                        <span class="mt-chg">{{ t.chgText }}</span>
                        <svg v-if="t.chart" class="mt-chart" viewBox="0 0 100 40" preserveAspectRatio="none" aria-hidden="true">
                            <polygon class="mt-area" :points="t.chart.area" />
                            <line class="mt-base" x1="0" x2="100" :y1="t.chart.base" :y2="t.chart.base" vector-effect="non-scaling-stroke" />
                            <polyline :points="t.chart.line" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke" />
                        </svg>
                    </li>
                </ul>
                <!-- 오늘의 경제 이슈(2026-11-22): 공개된 것이 있을 때만. 누르면 상세(+ 오늘 강했던 업종 TOP 3) -->
                <button v-if="issue" type="button" class="issue-card" @click="router.push(ISSUE_PATH)">
                    <span class="ic-head"><b>오늘의 경제 이슈</b><span>{{ issueDate }}</span></span>
                    <span v-if="issue.keywords.length" class="ic-kw"><span v-for="k in issue.keywords" :key="k">#{{ k }}</span></span>
                    <span class="ic-title">{{ issue.title }}</span>
                    <span class="ic-arrow" aria-hidden="true">›</span>
                </button>
            </section>

            <!-- 내 관심 종목: 담은 종목이 있을 때만 오늘 시장 바로 아래에(2026-11-22 오늘 시장을 맨 위로). 오늘 소식은 일봉으로 판단한다 -->
            <section v-if="watchRows.length" class="sec my-watch" aria-labelledby="my-watch-title">
                <div class="mw-box">
                    <div class="mw-head">
                        <h2 id="my-watch-title">내 관심 종목</h2>
                        <span v-if="watchlist.alerts" class="mw-tag">알림 켜짐</span>
                        <button v-else-if="canAskPush" type="button" class="mw-tag" @click="turnOnAlerts">알림 받기</button>
                    </div>
                    <ul>
                        <li v-for="w in watchRows" :key="w.code">
                            <span class="mw-text">
                                <b>{{ w.name }}</b>
                                <small :class="{ quiet: w.news.kind === 'quiet' || w.news.kind === 'none' }">{{ w.news.text }}</small>
                            </span>
                            <span class="mw-val"><b>{{ w.price }}</b><span v-if="w.pct" class="badge" :class="w.cls">{{ w.pct }}</span></span>
                            <WatchStar :code="w.code" :name="w.name" />
                        </li>
                    </ul>
                </div>
            </section>

            <!-- ── 2. AI 분석 종목 TOP(최대 3, 2026-11-22 '시장이 주목하는 종목'에서 이름 변경): 한 줄씩(순위 · 이름 · 가격 · 등락 배지). 줄을 누르면 AI 분석 ── -->
            <section class="sec watch" aria-labelledby="watch-title">
                <div class="sec-head">
                    <h2 id="watch-title">AI 분석 종목 TOP</h2>
                    <span v-if="basisText" class="meta">{{ basisText }}</span>
                </div>

                <div v-if="isLoading" class="w-skeleton" aria-busy="true" aria-label="불러오는 중">
                    <i v-for="n in 3" :key="n"></i>
                </div>
                <div v-else-if="!visibleRows.length" class="w-empty">
                    <p>오늘은 AI 기준에 충족된 종목이 없습니다.</p>
                    <button v-if="candidateCount" type="button" class="text-link" @click="router.push('/stock/preset')">설정 조정하기</button>
                </div>
                <ol v-else class="rows">
                    <li v-for="(w, i) in visibleRows" :key="w.code" class="w-li">
                        <component :is="canOpen(AI_PATH) ? 'button' : 'div'" :type="canOpen(AI_PATH) ? 'button' : undefined"
                            class="row line-row" :class="{ link: canOpen(AI_PATH) }" :aria-label="canOpen(AI_PATH) ? `${w.name} AI 분석 보기` : undefined"
                            @click="canOpen(AI_PATH) && goToStock(w.item)">
                            <span class="r-rank">{{ i + 1 }}</span>
                            <span class="line-name">{{ w.name }}</span>
                            <b class="line-price">{{ formatNumber(w.item.close) }}</b>
                            <span class="badge" :class="w.chg.cls">{{ w.pctText }}</span>
                        </component>
                        <WatchStar class="row-star" :code="w.code" :name="w.name" :close="w.item.close" :rate="w.pctText" />
                        <!-- 가장 주요한 추천 이유 1개(매수추천 탭과 같은 문장·같은 띠) -->
                        <component v-if="w.reasons.top" :is="canOpen(AI_PATH) ? 'button' : 'div'" :type="canOpen(AI_PATH) ? 'button' : undefined"
                            class="why" :class="{ link: canOpen(AI_PATH) }" tabindex="-1" @click="canOpen(AI_PATH) && goToStock(w.item)">
                            <span class="why-ic" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="m5 12.5 4.5 4.5L19 7.5"></path></svg></span>
                            <span class="why-tx">{{ w.reasons.top.text }}<em v-if="w.reasons.rest">+{{ w.reasons.rest }}</em></span>
                        </component>
                    </li>
                </ol>
                <button v-if="canOpen(BUY_TARGET_PATH)" type="button" class="more" @click="router.push(BUY_TARGET_PATH)">AI 분석 종목 전체 보기</button>
            </section>


            <!-- ── 3. 이번 주의 차트: 전 주 선정 종목 1개(2026-11-22 '성과' 섹션을 대체). 성과 숫자는 홈에 두지 않는다 ── -->
            <WeeklyChart />

            <!-- ── 4. 내 기준: 로그인·기준 상태별 3분기 — 2026-11-22 당분간 홈에서 뺌(컴포넌트·import 는 그대로 두고 주석 처리) ──
            <MyCriteria :is-logged-in="isLoggedIn" :has-criteria="persona.decided" :type="type"
                :matched-count="pick.matched_count || 0" :first-name="pick.items[0]?.stock_name || ''"
                :backtest-open="canOpen('/stock/backtest')" />
            -->

            <!-- ── 오늘의 꿀: 광고 자리와 공지사항 위(docs/points-plan.md) ── -->
            <section class="sec honey" aria-labelledby="honey-title">
                <div class="sec-head">
                    <h2 id="honey-title">오늘의 꿀</h2>
                    <button type="button" class="honey-more" @click="router.push(HONEY_PATH)">꿀 모으기 ›</button>
                </div>
                <HoneyTodayCard />
            </section>

            <!-- 광고 1자리: 공지사항 바로 위(AD_FREE 에게는 없다).
                 웹은 AdSlot(자리표시·테스트·애드센스), 앱은 AdMob 배너를 이 칸에 끼워 넣는다(AdInlineBanner, 2026-11-22) -->
            <section v-if="heroAdVisible" class="sec hero-ad" aria-label="광고">
                <AdSlot placement="homeHero" />
            </section>
            <section v-else-if="appAdVisible" class="sec hero-ad" aria-label="광고">
                <AdInlineBanner header-selector=".home-header" />
            </section>

            <!-- ── 공지사항: 최신 1줄만. 나머지는 '전체 보기' ── -->
            <section class="sec notice" aria-labelledby="notice-title">
                <div class="sec-head">
                    <h2 id="notice-title">공지사항</h2>
                    <button type="button" class="meta-link" @click="router.push(NOTICE_LIST_PATH)">전체 보기</button>
                </div>
                <p v-if="!notices.length" class="notice-empty">등록된 공지사항이 없습니다.</p>
                <button v-else type="button" class="notice-line" @click="goToNotice(notices[0])">
                    <span class="notice-cat">{{ notices[0].category }}</span>
                    <span class="notice-title">{{ notices[0].title }}</span>
                    <span class="notice-date">{{ noticeDateText(notices[0].created_date).slice(5) }}</span>
                </button>
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
 * 양봉상회 홈(2026-11-15 개편 1차, 2026-11-22 회의로 성과 삭제).
 * 순서: 시황 → AI 분석 종목 TOP(≤3) → 이번 주의 차트 → (내 기준: 주석 처리) → 공지.
 * 데이터는 기존 홈과 같은 API(전부 비로그인 허용)를 쓴다. 알고리즘·계산은 그대로다.
 *   - AI 분석 종목: 종목 이름·등락과 AI 분석·차트 확인 버튼만(근거·살 만한 가격·내 조건 충족은 2026-11-15 뺌).
 *   - 내 설정(보조지표 수치)으로 거르고 설정한 순서로 정렬하는 일은 서버가 한다(/stocks/buy-target/home, 2026-11-18).
 */
import AdSlot from '../common/AdSlot.vue';
import AdInlineBanner from '../common/AdInlineBanner.vue';
import WeeklyChart from './WeeklyChart.vue';
// import MyCriteria from './MyCriteria.vue';   // 내 기준 카드 — 홈에서 뺌(2026-11-22). 다시 쓸 때 위 템플릿 주석과 함께 푼다
import aibeesApi from '@scripts/aibeesApi.js';
import { assUserSession } from '@scripts/stores/user-stores.js';
import { usePersonaStore } from '@scripts/stores/persona-store.js';
import { hasRole, WORKER_ROLE } from '@scripts/useAccess.js';
import { useShowAds } from '@scripts/useAds.js';
import { isNativeAdsEnabled } from '@scripts/useAdMob.js';
import { INTRO_PATH, isGuestPath } from '@scripts/authPaths.js';
import { NOTICE_LIST_PATH, NOTICE_DETAIL_PATH, noticeDateText } from '@scripts/notice.js';
import { numOrNull, formatNumber, changeInfo } from '@scripts/stockSignals.js';
import { marketWeather, dailyRate } from '@scripts/persona.js';
import { judgeStockNews, itemFromChart } from '@scripts/stockNews.js';
import { useWatchlistStore } from '@scripts/stores/watchlist-store.js';
import { HONEY_PATH, ISSUE_PATH } from '@scripts/support.js';
import { issueDateText } from '@/components/Issue/issueText.js';
import { enablePushNotifications } from '@scripts/usePushNotifications.js';
import { Capacitor } from '@capacitor/core';

const router = useRouter();
const userSession = assUserSession();
const persona = usePersonaStore();

const isLoggedIn = computed(() => !!userSession.user.accessToken);
const userName = computed(() => userSession.getUserInfo || '');
const userInitial = computed(() => (userName.value?.[0] ?? '?').toUpperCase());
const isWorker = computed(() => hasRole(WORKER_ROLE));
const showAds = useShowAds();

// 웹 광고 칸(AdSlot). 앱은 AdSlot 이 자리표시만 그리므로 아래 appAdVisible 의 AdMob 배너가 대신한다.
const heroAdVisible = computed(() => !isWorker.value && showAds.value && !isNativeAdsEnabled());
// 앱은 화면 안 AdMob 배너(앱 안 플러그인 InlineAd)로 같은 자리를 채운다.
const appAdVisible = computed(() => !isWorker.value && showAds.value && isNativeAdsEnabled());

// 종목 상세(/stock/info)는 로그인 사용자만 쓴다(2026-11-20). 메뉴가 열려 있으면 비로그인에게도 행을 누를 수 있게 그리고,
// 누르면 라우터 가드가 로그인 화면으로 안내한 뒤 로그인하면 그 종목으로 돌려보낸다(authPaths.rememberAfterLogin).
const canOpenDetail = computed(() => userSession.access.paths.includes('/stock/info'));

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
        // extra=us10y: 달러 금리(미국 10년물)를 함께 받는다 — 비밀상회 홈과 같은 API 라 요청할 때만 붙는다
        const { data } = await aibeesApi.get('/api/v1/indicators/market-snapshot', { params: { extra: 'us10y' } });
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
// 지수 줄은 코스피·코스닥만(원/달러·달러 금리는 아래 따로 그린다)
const NON_INDEX_KEYS = ['usdkrw', 'us10y'];
const indexCards = computed(() => marketData.value.filter(m => !NON_INDEX_KEYS.includes(m.key)).map(m => {
    const r5 = numOrNull(m.rate_5d);
    const r20 = numOrNull(m.rate_20d);
    const r1 = dailyRate(m);   // 서버 필드는 rate(전일 대비 %). 없으면 spark 마지막 두 값으로 계산
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
    const chgPart = change !== null && dir !== 0 ? `${signed(change, 2)} ` : (rate !== null && dir !== 0 ? `${dir > 0 ? '+' : '−'}` : '');  // 예) −4.70 (0.34%)
    return {
        priceText: priceText(m.price),
        // 미니 차트 색은 지수와 같이 20일 흐름 기준
        sparkPoints: sparkPoints(m.spark),
        sparkCls: clsOf(m.rate_20d),
        chgText: rate === null ? '' : `${chgPart}(${Math.abs(rate).toFixed(2)}%)`,
        pctText: rate === null ? '' : `${signed(rate, 1)}%`,
        cls: clsOf(rate),
    };
});
// 달러 금리: 값은 %, 오늘 등락은 금리 자체의 차이(%p). 미니 차트 색은 20거래일 전보다 올랐는지로.
const usRateItem = computed(() => {
    const m = marketData.value.find(x => x.key === 'us10y');
    const price = numOrNull(m?.price);
    if (!m || price === null) return null;
    const change = numOrNull(m.change);
    const spark = (m.spark || []).map(numOrNull).filter(v => v !== null);
    return {
        priceText: `${price.toFixed(2)}%`,
        chgText: change === null ? '' : `${signed(change, 2)}%p`,
        cls: clsOf(change === null ? 0 : Math.round(change * 100) / 100),
        sparkPoints: sparkPoints(m.spark),
        sparkCls: clsOf(spark.length >= 2 ? spark.at(-1) - spark[0] : 0),
    };
});
const weather = computed(() => marketWeather(marketData.value));

/* ── 오늘의 경제 이슈 ── GET /api/v1/daily-issue (공개된 것만, 비로그인 허용). 없거나 실패하면 카드를 숨긴다 */
const issue = ref(null);
const loadIssue = async () => {
    try {
        const { data } = await aibeesApi.get('/api/v1/daily-issue');
        issue.value = data?.data?.issue ?? null;
    } catch { issue.value = null; }
};
const issueDate = computed(() => issueDateText(issue.value?.ymd));

// 옆으로 넘기는 시장 카드용 차트: 선 + 옅은 면 + 기간 첫 값 점선(기준선). viewBox 100×40
const tileChart = (values) => {
    const vs = (values || []).map(numOrNull).filter(v => v !== null);
    if (vs.length < 2) return null;
    const min = Math.min(...vs);
    const span = Math.max(...vs) - min || 1;
    const y = (v) => (36 - (v - min) / span * 32).toFixed(1);
    const pts = vs.map((v, i) => `${(i / (vs.length - 1) * 100).toFixed(1)},${y(v)}`);
    return { line: pts.join(' '), area: `0,40 ${pts.join(' ')} 100,40`, base: y(vs[0]) };
};
// 지수 오늘 변동폭: 서버가 change 를 주지 않으면 현재가와 등락률로 계산한다
const indexChange = (m, r1) => {
    const c = numOrNull(m.change);
    if (c !== null) return c;
    const p = numOrNull(m.price);
    return p === null || r1 === null ? null : p - p / (1 + r1 / 100);
};
const marketTiles = computed(() => {
    const out = [];
    const rate = marketData.value.find(x => x.key === 'us10y');
    if (usRateItem.value) out.push({ key: 'us10y', label: '달러 금리', priceText: usRateItem.value.priceText, chgText: usRateItem.value.chgText, cls: usRateItem.value.cls, chart: tileChart(rate?.spark) });
    for (const m of marketData.value.filter(x => !NON_INDEX_KEYS.includes(x.key))) {
        const r1 = dailyRate(m);
        const c = indexChange(m, r1);
        out.push({
            key: m.key, label: INDEX_LABEL[m.key] ?? m.label ?? m.code, priceText: priceText(m.price),
            chgText: r1 === null ? '' : (c === null ? `${signed(r1, 2)}%` : `${signed(c, 2)} (${Math.abs(r1).toFixed(2)}%)`),
            cls: clsOf(r1), chart: tileChart(m.spark),
        });
    }
    const fx = marketData.value.find(x => x.key === 'usdkrw');
    if (fxItem.value) out.push({ key: 'usdkrw', label: '원/달러', priceText: fxItem.value.priceText, chgText: fxItem.value.chgText, cls: fxItem.value.cls, chart: tileChart(fx?.spark) });
    return out;
});


/* ── 2. AI 분석 종목 ── (날짜를 보내지 않으면 서버가 가장 최근 표시일을 고른다)
 *   2026-11-15 '시장이 주목하는 회사'(근거·살 만한 가격·내 조건 충족)에서 되돌림: 종목 이름·등락과 AI 분석·차트 확인 버튼만. */
const HOME_COUNT = 3;
const AI_PATH = '/stock/info';
const BUY_TARGET_PATH = '/stock/buy-target';
// 비로그인 공개 경로(authPaths.GUEST_PATHS)거나 서버가 이 사용자에게 허용한 메뉴면 버튼을 보인다.
const canOpen = (path) => isGuestPath(path) || userSession.access.paths.includes(path);

const type = computed(() => persona.currentType);

/* 서버가 내 설정으로 판정·정렬해 최대 HOME_COUNT 줄만 준다(/stocks/buy-target/home, 2026-11-18).
 * 예전에는 /stocks/buy-target 전체(종목당 120일 봉)를 받아 여기서 indicators.evaluate·persona.orderForType·recoReasons 로
 * 다시 계산했다. 판정 로직의 정본은 여전히 그 JS 이고, 서버(HomePickService)는 같은 결과를 내도록 옮긴 것이다. */
const EMPTY_PICK = { ymd: null, candidate_count: 0, matched_count: 0, items: [], watch_items: [] };
const pick = ref(EMPTY_PICK);
const isLoading = ref(true);
const watchlist = useWatchlistStore();
const watchCodes = computed(() => watchlist.items.map(w => w.code).join());
let pickSeq = 0;   // 설정을 빠르게 바꿀 때 늦게 온 옛 응답이 덮어쓰지 않게
const loadItems = async () => {
    const seq = ++pickSeq;
    isLoading.value = true;
    try {
        const { data } = await aibeesApi.get('/api/v1/stocks/buy-target/home', {
            // watch: 관심 종목 중 오늘 후보에 있는 것은 서버가 봉·내 조건 판정(match)을 같이 준다
            params: { settings: JSON.stringify(type.value.settings), limit: HOME_COUNT, watch: watchCodes.value || undefined },
        });
        if (seq !== pickSeq) return;
        const d = data?.data;
        pick.value = d && Array.isArray(d.items) ? { ...EMPTY_PICK, ...d } : EMPTY_PICK;
    } catch (e) {
        if (seq !== pickSeq) return;
        console.error('[home] AI 분석 종목 조회 실패', e);
        pick.value = EMPTY_PICK;
    } finally {
        if (seq === pickSeq) isLoading.value = false;
    }
};

const candidateCount = computed(() => pick.value.candidate_count || 0);
const visibleRows = computed(() => pick.value.items.map(item => {
    const pct = numOrNull(item.rate_pct);
    return {
        item,
        code: item.stock_code,
        name: item.stock_name,
        chg: { cls: clsOf(pct) },
        pctText: pct === null ? '–' : `${signed(pct, 2)}%`,
        reasons: { top: item.reason ? { text: item.reason } : null, rest: item.reason_rest || 0 },   // 가장 주요한 추천 이유 1개를 띠로
    };
}));
const basisText = computed(() => {
    const ymd = pick.value.ymd;
    return ymd ? `${mdText(String(ymd).replaceAll('-', ''))} 종가 기준` : '';
});
// 설정(유형)이나 관심 종목이 바뀌면 서버에 다시 묻는다.
watch(() => [JSON.stringify(type.value.settings), watchCodes.value], () => loadItems());

/* ── 내 관심 종목 ── */
const canAskPush = Capacitor.isNativePlatform();
const turnOnAlerts = async () => watchlist.setAlerts(await enablePushNotifications());
// 오늘 분석 목록에 있는 관심 종목: 서버가 준 후보 행(봉 포함) + match. code → 항목
const listedWatch = computed(() => new Map((pick.value.watch_items || []).map(x => [x.stock_code, x])));
// 오늘 분석 목록에서 빠진 관심 종목은 일봉을 따로 받아 같은 기준으로 판단한다. code → 항목(실패 시 null)
const watchCharts = ref({});
watch(() => [isLoading.value, watchCodes.value], () => {
    if (isLoading.value) return;
    watchlist.items
        .filter(w => !listedWatch.value.has(w.code) && !(w.code in watchCharts.value))
        .forEach(async (w) => {
            watchCharts.value = { ...watchCharts.value, [w.code]: undefined };
            let item = null;
            try {
                const { data } = await aibeesApi.get('/api/v1/charts/stock', { params: { stock_code: w.code, period: 'day' } });
                item = itemFromChart(w.code, w.name, data?.data);
            } catch (e) {
                console.warn('[watchlist] 일봉 조회 실패', w.code, e?.message);
            }
            watchCharts.value = { ...watchCharts.value, [w.code]: item };
        });
}, { immediate: true });

const watchRows = computed(() => watchlist.items.map((w) => {
    const listed = listedWatch.value.get(w.code);
    const item = listed ?? watchCharts.value[w.code];
    if (!item) {
        const failed = !isLoading.value && watchCharts.value[w.code] === null;
        return { code: w.code, name: w.name, price: w.close ? formatNumber(w.close) : '–', pct: '', cls: 'flat',
            news: { kind: 'none', text: failed ? '소식을 불러오지 못했어요' : '소식을 확인하고 있어요' } };
    }
    const chg = changeInfo(item);
    return {
        code: w.code, name: w.name, price: formatNumber(item.close), cls: chg.cls,
        pct: chg.pct === null ? '' : `${signed(chg.pct, 2)}%`,
        // 내 조건 판정은 분석 목록 종목만 한다(서버가 내 설정으로 판정한 match)
        news: judgeStockNews(item, listed ? { match: !!listed.match } : null),
    };
}));

const goToStock = (item) => router.push({
    path: AI_PATH,
    query: { stock_code: item.stock_code, stock_name: item.stock_name, ymd: String(item.ymd ?? '').replaceAll('-', '') },
});

/* '지난달 성과'는 2026-11-22 회의로 홈에서 뺐다(성과 숫자는 백테스트 안의 비교로만 남긴다). */

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
    loadIssue();
    marketTimer = setInterval(loadMarketSnapshot, 60 * 1000);
    loadItems();
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
.notice-list li:last-child .notice-row { border-bottom: 0 !important; }
.notice-row {
    .notice-title { font-size: 15px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .notice-cat { width: auto; margin-right: 6px; font-size: 15px; font-weight: 600; color: $amber-700; }
    .notice-date { margin-left: 0; font-size: 13px; color: $sub; }
}
.notice { padding-bottom: 8px; }
.simple-foot .notes { color: $sub; }

/* ── 2026-11-17 v3 '숨 쉬는 버전': 줄마다 한 줄, 섹션 위 여백 32px, 회색 보조 줄 최소화 ── */
.sec { padding-top: 32px; padding-bottom: 12px; }
.market { padding-top: 16px; }
.sec-head { align-items: center; margin-bottom: 12px; h2 { display: inline-flex; align-items: center; gap: 6px; } }
.weather { margin-top: 0; margin-bottom: 8px; }
.rows { margin-top: 0; }
.more { margin-top: 12px; margin-bottom: -12px; }

// 지수: 이름 · 미니 차트 · 지수 · 오늘 등락
.idx-row { min-height: 56px; gap: 12px; }
.idx-name { flex: 1; min-width: 0; font-size: 16px; color: $sub-ink; }
.idx-spark { width: 48px; height: 20px; flex: none; }
.idx-price { flex: none; min-width: 84px; text-align: right; font-size: 16px; font-weight: 600; }
// 오늘 등락은 TOP 3 와 같은 .badge(빨강·파랑 둥근 박스)로 통일

// 오늘의 경제 이슈 카드(오늘 시장 안, 지표 카드 아래)
.issue-card {
    position: relative; display: block; width: 100%; box-sizing: border-box; margin-top: $gap;
    padding: $card-pad 40px $card-pad $card-pad; border: 0; border-radius: $radius; background: $bg;
    color: inherit; font: inherit; letter-spacing: inherit; text-align: left; cursor: pointer;
}
.ic-head { display: flex; align-items: baseline; gap: 8px; font-size: 13px; color: $sub; b { font-size: 13.5px; color: $amber-700; } }
.ic-kw { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; span { padding: 2px 8px; border-radius: 8px; background: $card; border: 1px solid $line; font-size: 12px; font-weight: 700; color: $sub-ink; } }
.ic-title { display: block; margin-top: 8px; font-size: 16px; font-weight: 700; line-height: 1.45; word-break: keep-all; }
.ic-arrow { position: absolute; right: $card-pad; top: 50%; transform: translateY(-50%); font-size: 20px; color: $sub; }


// 오늘 시장: 옆으로 넘기는 카드(2026-11-22). 폰은 2장 반이 보여 넘길 수 있다는 걸 알리고, 넓은 화면은 4장이 나란히 채운다
.mkt-tiles {
    display: flex; gap: 10px; margin: 4px (-$pad-x) 0; padding: 4px $pad-x 8px; list-style: none;
    overflow-x: auto; scroll-snap-type: x mandatory; scroll-padding: 0 $pad-x; -webkit-overflow-scrolling: touch;
    scrollbar-width: none; &::-webkit-scrollbar { display: none; }
}
.mkt-tile {
    flex: 1 0 128px; min-width: 128px; scroll-snap-align: start; box-sizing: border-box;
    padding: 14px 14px 12px; border: 1px solid $line; border-radius: 14px; background: $card;
    display: flex; flex-direction: column; color: $sub-ink;
    &.up { color: $up; } &.down { color: $down; }
}
.mt-name { font-size: 14px; color: $sub-ink; }
.mt-price { margin-top: 4px; font-size: 19px; font-weight: 700; color: $ink; letter-spacing: -0.4px; white-space: nowrap; font-variant-numeric: tabular-nums; }
.mt-chg { margin-top: 2px; min-height: 18px; font-size: 13px; font-weight: 600; white-space: nowrap; font-variant-numeric: tabular-nums; }
.mt-chart { display: block; width: 100%; height: 44px; margin-top: 10px; }
.mt-area { fill: currentColor; opacity: .08; }
.mt-base { stroke: $sub; stroke-width: 1; stroke-dasharray: 2 3; opacity: .6; }

// 한 줄 종목: 순위 · 이름 · 가격 · 배지
.line-row {
    width: 100%;
    box-sizing: border-box;
    min-height: 56px;
    gap: 12px;
    padding: 0;
    border: 0;
    background: transparent;
    color: inherit;
    text-align: left;
    &.link { cursor: pointer; }
    .r-rank { width: 16px; }
}
.line-name { flex: 1; min-width: 0; font-size: 16px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.line-price { flex: none; font-size: 16px; font-weight: 600; }
.line-sub { flex: none; font-size: 13px; color: $sub; }
.badge { height: 24px; min-width: 62px; justify-content: center; }

// 공지: 최신 1줄
.notice { padding-top: 24px; padding-bottom: 8px; .sec-head { margin-bottom: 4px; } }
.notice-line {
    width: 100%;
    min-height: 48px;
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 0;
    border: 0;
    background: transparent;
    color: $ink;
    text-align: left;
    cursor: pointer;
    .notice-cat { flex: none; font-size: 15px; font-weight: 600; color: $amber-700; }
    .notice-title { flex: 1; min-width: 0; font-size: 15px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .notice-date { flex: none; font-size: 13px; color: $sub; }
}

/* 날씨 그림: 이모지 스타일 이미지 — 크림 바탕 칸 */
.weather .wx-box { width: 48px; height: 48px; border-radius: $radius; background: $honey-50; }
.weather .wx-img { width: 36px; height: 36px; display: block; }

/* ── TOP 3 추천 이유 띠 + 꿀빛 그라데이션(한국투자 AI 말풍선 참고, 노랑 계열 안에서만) ── */
.w-li { padding-bottom: 12px; .line-row { min-height: 48px; } }
.why {
    width: calc(100% - 28px);
    box-sizing: border-box;
    margin-left: 28px;
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 12px;
    border: 0;
    border-radius: 10px;
    background: $honey-strip;
    color: $honey-ink;
    text-align: left;
    &.link { cursor: pointer; }
}
.why-ic {
    flex: none;
    width: 18px;
    height: 18px;
    border-radius: 9px;
    background: $honey-dot;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    svg { width: 10px; height: 10px; fill: none; stroke: $honey-ink; stroke-width: 2.6; stroke-linecap: round; stroke-linejoin: round; }
}
.why-tx {
    flex: 1;
    min-width: 0;
    font-size: 14px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    em { font-style: normal; margin-left: 4px; font-weight: 600; color: $amber-700; }
}
/* ── 내 관심 종목 ── */
// 2026-11-22 노란 상자 제거: 다른 섹션처럼 흰 섹션 하나로(제목 크기도 통일)
.my-watch { padding-bottom: 16px; }
.mw-box { ul { margin: 8px 0 0; padding: 0; list-style: none; } li { min-height: 58px; display: flex; align-items: center; gap: 8px; } }
.mw-head { display: flex; align-items: center; justify-content: space-between; h2 { margin: 0; font-size: 20px; font-weight: 700; letter-spacing: -0.5px; } }
.mw-tag { height: 24px; padding: 0 7px; border: 0; border-radius: $radius-sm; background: $honey-100; color: $amber-700; font-size: 11px; font-weight: 700; display: inline-flex; align-items: center; }
.mw-text { flex: 1; min-width: 0; b { display: block; font-size: 15px; font-weight: 600; } small { display: block; margin-top: 3px; font-size: 12.5px; color: $honey-ink; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; &.quiet { color: $sub; } } }
.mw-val { flex: none; display: flex; flex-direction: column; align-items: flex-end; gap: 3px; b { font-size: 14px; font-weight: 600; } .badge { height: 21px; min-width: 56px; font-size: 12px; } }
.w-li { position: relative; .line-row { padding-right: 32px; } }
.row-star { position: absolute; top: 7px; right: -6px; }

/* ── 오늘의 꿀 ── */
.honey .sec-head { display: flex; justify-content: space-between; align-items: center; }
.honey .sec-head h2 { white-space: nowrap; }
.honey-more { flex: none; border: 0; background: transparent; padding: 0; font: inherit; font-size: 13.5px; color: $sub; font-weight: 600; cursor: pointer; }

/* ══ 2026-11-22 간격 통일(8px 격자, 토큰: _home-tokens.scss) — 위의 섹션별 값보다 이 블록이 우선 ══
   섹션 위아래 24 · 제목→내용 12 · 한 줄 56 · 보조 줄이 붙는 줄 48(+보조 줄+12) · 카드 안쪽 16 · 사이 12 */
.sec, .market, .my-watch, .notice, .hero-ad { padding-top: $sec-pt; padding-bottom: $sec-pb; }
.sec-head, .mw-head, .notice .sec-head { margin-bottom: $head-gap; }
.rows, .mw-box ul, .notice-list { margin: 0; }
.weather { margin: 0 0 $gap; }
.mkt-tiles { margin: 0 (-$pad-x); padding: 0 $pad-x; gap: $gap; }
.mkt-tile { padding: $card-pad; }
.line-row, .mw-box li, .notice-line { min-height: $row-h; }
.w-li { padding: 0 0 $gap; .line-row { min-height: $row-h-sub; } &:last-child { padding-bottom: 0; } }
.more { margin-top: $gap; margin-bottom: -$sec-pb; }
.sec-head .meta-link { margin: -4px 0; }   // 누르기 쉬운 32px 링크가 제목 줄을 밀지 않게
</style>
