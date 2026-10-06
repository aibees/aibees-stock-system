<template>
    <div id="home">

        <!-- ════════ 상단: 로고 칩 + 즐겨찾기 + 계정, 아래에 12px 차양 띠 ════════
             모바일에서는 sticky(+세이프 에어리어), 데스크톱은 상단 내비(Lnb)가 브랜드를 보여준다. -->
        <header class="home-header" data-ad-anchor>
            <div class="hh-row">
                <button type="button" class="brand-chip" @click="router.push('/home')" aria-label="양봉상회 홈">
                    <img class="brand-logo" src="/favicon.svg" alt="" aria-hidden="true" />
                    <span class="brand-name">양봉상회</span>
                </button>

                <div class="hh-actions">
                    <button type="button" class="icon-btn" aria-label="즐겨찾기" @click="goFavorites">
                        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round" aria-hidden="true"><path d="m12 3 2.7 5.6 6.1.8-4.5 4.2 1.1 6L12 16.7 6.6 19.6l1.1-6-4.5-4.2 6.1-.8z"></path></svg>
                    </button>

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
            <div class="awning" aria-hidden="true"></div>
        </header>

        <main class="home-main">

            <!-- ── 날짜 네비게이터: ‹ 날짜(요일) › + 장 상태 ── -->
            <div class="date-nav">
                <button type="button" class="nav-btn" aria-label="이전 영업일" @click="stepSelectedDate(-1)">‹</button>
                <div class="date-center">
                    <button type="button" class="date-btn" aria-label="날짜 선택" @click="openDatePicker">
                        <span class="date-main">{{ dateLabel }}</span>
                        <span class="date-status" :class="marketState"><i class="dot"></i>{{ statusLabel }}</span>
                    </button>
                    <input type="date" ref="dateInput" class="hidden-input" v-model="selectedDate"
                        @change="handleDateChange" tabindex="-1" aria-hidden="true" />
                </div>
                <button type="button" class="nav-btn" aria-label="다음 영업일" @click="stepSelectedDate(1)">›</button>
            </div>

            <!-- ── 최우선 타겟 히어로 ── -->
            <section class="priority-hero" aria-label="오늘의 최우선 타겟">
                <div class="ph-top">
                    <span class="ph-badge">오늘의 최우선 타겟</span>
                    <button v-if="isLoggedIn && sortedData.length" type="button" class="ph-change" @click="sheetOpen = true">
                        {{ priorityTarget ? '다른 타겟' : '타겟 고르기' }} ▾
                    </button>
                </div>

                <template v-if="priorityItem">
                    <div class="ph-body">
                        <div class="ph-who">
                            <span class="ph-name">{{ priorityItem.stock_name }}</span>
                            <span class="ph-code">{{ priorityItem.stock_code }}</span>
                        </div>
                        <div class="ph-px">
                            <span class="ph-price">{{ formatNumber(priorityItem.close) }}</span>
                            <span class="ph-chg" :class="changeInfo(priorityItem).cls">{{ changeInfo(priorityItem).text }}</span>
                        </div>
                    </div>
                    <p class="ph-reason">{{ reasonLine(priorityItem) }}</p>
                    <button type="button" class="ph-cta" @click="goToStockInfo(priorityItem.stock_code, priorityItem.stock_name)">AI 분석 보기</button>
                </template>

                <!-- 다른 날짜에서 지정해 지금 목록에는 없는 경우: 이름만 -->
                <template v-else-if="priorityTarget">
                    <div class="ph-body">
                        <div class="ph-who">
                            <span class="ph-name">{{ priorityTargetName || priorityTarget }}</span>
                            <span class="ph-code">{{ priorityTarget }}</span>
                        </div>
                    </div>
                    <p class="ph-reason">다른 날짜에서 지정한 타겟이에요. 이 날짜의 추천 목록에는 없습니다.</p>
                    <button type="button" class="ph-cta" @click="goToStockInfo(priorityTarget, priorityTargetName)">AI 분석 보기</button>
                </template>

                <template v-else-if="isLoading">
                    <div class="ph-skeleton"></div>
                </template>

                <template v-else>
                    <p class="ph-empty">
                        {{ isLoggedIn ? '추천 종목 중 하나를 최우선 타겟으로 정해 두면 여기에 보여드려요.' : '로그인하면 추천 종목 중 최우선 타겟을 직접 정할 수 있어요.' }}
                    </p>
                    <button v-if="isLoggedIn && sortedData.length" type="button" class="ph-cta" @click="sheetOpen = true">타겟 고르기</button>
                    <button v-else-if="!isLoggedIn" type="button" class="ph-cta" @click="router.push('/login')">로그인</button>
                </template>
            </section>

            <!-- 모바일 전용 광고(리스트 위). 데스크톱은 사이드 배너, AD_FREE 는 안 보임. -->
            <AdBanner />

            <!-- ── 추천 종목 리스트 ── -->
            <section class="reco" aria-label="추천 종목">
                <div class="list-head">
                    <h2>추천 종목 <span class="count">{{ sortedData.length }}</span></h2>
                    <div class="list-tools">
                        <label class="sort-pill">
                            <select v-model="sortKey" @change="onSortKeyChange" aria-label="정렬 기준">
                                <option v-for="o in SORT_OPTIONS" :key="o.key" :value="o.key">{{ o.label }}</option>
                            </select>
                            <span class="pill-text" aria-hidden="true">{{ currentSort.label }} ▾</span>
                        </label>
                        <button type="button" class="dir-btn" @click="toggleSortDir"
                            :aria-label="sortDir === 'desc' ? currentSort.descLabel : currentSort.ascLabel"
                            :title="sortDir === 'desc' ? currentSort.descLabel : currentSort.ascLabel">
                            {{ sortDir === 'desc' ? '↓' : '↑' }}
                        </button>
                    </div>
                </div>

                <div v-if="!isLoading && rows.length" class="reco-list">
                    <div v-for="(r, idx) in rows" :key="r.item.stock_code ?? idx" class="reco-item">
                        <button type="button" class="reco-row" :class="{ open: expandedCode === r.item.stock_code }"
                            :aria-expanded="expandedCode === r.item.stock_code ? 'true' : 'false'"
                            @click="toggleRow(r.item.stock_code)">
                            <span class="rank">{{ String(idx + 1).padStart(2, '0') }}</span>
                            <span class="who">
                                <span class="name-line">
                                    <span class="name">{{ r.item.stock_name }}</span>
                                    <span class="code">{{ r.item.stock_code }}</span>
                                    <span v-if="r.item.stock_code === priorityTarget" class="pri-chip">최우선</span>
                                </span>
                                <span class="reason">{{ r.reason }}</span>
                            </span>
                            <span class="px">
                                <span class="price">{{ formatNumber(r.item.close) }}</span>
                                <span class="chg" :class="r.chg.cls">{{ r.chg.text }}</span>
                            </span>
                        </button>

                        <div v-if="expandedCode === r.item.stock_code" class="reco-detail">
                            <!-- 시/고/저/종 + 거래량 표 (장중에는 '종가' 대신 '현재가') -->
                            <table class="ohlc">
                                <thead>
                                    <tr><th>시가</th><th>고가</th><th>저가</th><th>{{ priceLabel }}</th></tr>
                                </thead>
                                <tbody>
                                    <tr>
                                        <td>{{ formatNumber(r.item.open) }}</td>
                                        <td class="hi">{{ formatNumber(r.item.high) }}</td>
                                        <td class="lo">{{ formatNumber(r.item.low) }}</td>
                                        <td class="cl">{{ formatNumber(r.item.close) }}</td>
                                    </tr>
                                    <tr class="vol">
                                        <th colspan="2" scope="row">거래량</th>
                                        <td colspan="2">{{ formatNumber(r.item.volume) }}</td>
                                    </tr>
                                </tbody>
                            </table>
                            <!-- 점수가 아직 없으면(장 마감 후 산출) 칸 자체를 숨긴다 -->
                            <div v-if="hasValue(r.item.score)" class="score-line">종합 점수 <b>{{ numOrNull(r.item.score) }}</b> / 100</div>

                            <div class="rd-actions">
                                <button type="button" class="btn-outline strong" @click="goToStockInfo(r.item.stock_code, r.item.stock_name)">AI 분석</button>
                                <button type="button" class="btn-outline" @click="toggleChart(r.item.stock_code)">
                                    {{ expandedCharts.has(r.item.stock_code) ? '차트 접기' : '차트' }}
                                </button>
                            </div>

                            <!-- 간이 차트: 최근 120영업일 봉차트 + 20/60/120일선 -->
                            <div v-if="expandedCharts.has(r.item.stock_code) && r.item.chart_data && r.item.chart_data.length" class="mini-chart">
                                <div class="mini-chart-head">
                                    <div class="mini-legend">
                                        <span class="leg-item" style="--c:#efa55b">MA20</span>
                                        <span class="leg-item" style="--c:#8bb400">MA60</span>
                                        <span class="leg-item" style="--c:#01b6f3">MA120</span>
                                    </div>
                                    <button type="button" class="mini-chart-detail" @click="goToChart(r.item.stock_code)">자세히보기 ›</button>
                                </div>
                                <div class="mini-chart-canvas">
                                    <CandlestickChart :chartData="buyTargetCandleData(r.item)" :extraOptions="miniCandleOptions" />
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- 홈에는 상위 3개만. 전체 목록은 매수추천 메뉴에서 본다. -->
                    <button type="button" class="more-btn" @click="goToBuyTarget">
                        전체 {{ sortedData.length }}개 자세히보기 ›
                    </button>
                </div>

                <div v-else-if="isLoading" class="reco-list">
                    <div class="skeleton-row" v-for="n in 4" :key="n"></div>
                </div>

                <div v-else class="empty-box">
                    <p>분석된 데이터가 없습니다. 날짜를 변경해 보세요.</p>
                </div>
            </section>

            <p class="disclaimer">본 정보는 투자 권유가 아니며, 투자 판단의 책임은 투자자 본인에게 있습니다.</p>
        </main>

        <!-- ── 최우선 타겟 선택 시트 ── -->
        <teleport to="body">
            <transition name="sheet">
                <div v-if="sheetOpen" class="sheet-overlay" @click.self="sheetOpen = false">
                    <div class="sheet" role="dialog" aria-modal="true" aria-label="최우선 타겟 선택">
                        <div class="sheet-head">
                            <strong>최우선 타겟 선택</strong>
                            <button type="button" class="sheet-close" aria-label="닫기" @click="sheetOpen = false">✕</button>
                        </div>
                        <ul class="sheet-list">
                            <li>
                                <button type="button" class="sheet-item" :class="{ on: !priorityTarget }" @click="selectPriority(null)">
                                    <span class="si-name">선택 안 함</span>
                                </button>
                            </li>
                            <li v-for="(item, i) in sortedData" :key="item.stock_code">
                                <button type="button" class="sheet-item" :class="{ on: item.stock_code === priorityTarget }" @click="selectPriority(item.stock_code)">
                                    <span class="si-rank">{{ String(i + 1).padStart(2, '0') }}</span>
                                    <span class="si-name">{{ item.stock_name }} <em>{{ item.stock_code }}</em></span>
                                    <span class="si-chg" :class="changeInfo(item).cls">{{ changeInfo(item).text }}</span>
                                </button>
                            </li>
                        </ul>
                    </div>
                </div>
            </transition>
        </teleport>
    </div>
</template>

<script setup>
import CandlestickChart from './common/comp/CandlestickChart.vue';
import AdBanner from './common/AdBanner.vue';
import aibeesApi from '@scripts/aibeesApi.js';
import { assUserSession } from '@scripts/stores/user-stores.js';
import {
    numOrNull, formatNumber, hasValue, changeInfo, reasonLine,
    kstNowParts, isMarketOpenNow, weekdayKo, toYmdString, shiftDate, getLatestBatchDate,
} from '@scripts/stockSignals.js';

const router = useRouter();
const userSession = assUserSession();
// 홈은 비로그인도 열린다. 최우선타겟처럼 계정에 묶인 기능은 로그인했을 때만 쓴다.
const isLoggedIn = computed(() => !!userSession.user.accessToken);
const userName = computed(() => userSession.getUserInfo || '');
const userInitial = computed(() => (userName.value?.[0] ?? '?').toUpperCase());

/* ── 이동 ── */
const goToStockInfo = (stock_code, stock_name) => {
    // ymd: 상세 화면이 같은 날짜의 매수타겟 행(근거·재무·조건)을 찾는 데 쓴다.
    router.push({ path: '/stock/info', query: { stock_code, stock_name, ymd: selectedDate.value.replaceAll('-', '') } });
};
const goToChart = (stock_code) => {
    router.push({ path: '/stock/chart', query: { code: stock_code } });
};
const goTo = (path) => { menuOpen.value = false; router.push(path); };
const goFavorites = () => {
    if (!isLoggedIn.value) {
        alert('로그인이 필요한 페이지입니다. 로그인메뉴로 이동합니다.');
        router.push({ name: 'login' });
        return;
    }
    router.push({ name: 'group' });
};

/* ── 계정 메뉴 ── */
const menuOpen = ref(false);
const accountRef = ref(null);
const onDocClick = (e) => {
    if (menuOpen.value && accountRef.value && !accountRef.value.contains(e.target)) menuOpen.value = false;
};
const onKeyDown = (e) => { if (e.key === 'Escape') { menuOpen.value = false; sheetOpen.value = false; } };
const logout = () => {
    menuOpen.value = false;
    userSession.logoutUser();      // pinia + sessionStorage + localStorage 초기화
    router.push('/login');
};

const resultData = ref([]);
const isLoading = ref(true);

/* ── 장 상태 ──
 * 선택한 날짜가 오늘(KST)이고 정규장(평일 09:00~15:30)이면 "장중". 그 외에는 마감 데이터다.
 * ※ 공휴일은 반영하지 않는다(TODO: 휴장일 데이터가 생기면 연동). */
const nowKst = ref(kstNowParts());
let clock = null;

const selectedDate = ref(getLatestBatchDate());
const dateInput = ref(null);

const todayDash = computed(() => toYmdString(nowKst.value.year, nowKst.value.month, nowKst.value.day));
const marketState = computed(() =>
    selectedDate.value === todayDash.value && isMarketOpenNow(nowKst.value) ? 'live' : 'closed');

const dateLabel = computed(() => {
    const [, m, d] = selectedDate.value.split('-');
    return `${m}.${d} (${weekdayKo(selectedDate.value)})`;
});
// 장중: '종가'라는 말을 쓰지 않는다(현재가와 같은 값이라 오해를 부른다). 마감 후: 종가 · MM/DD 마감.
const statusLabel = computed(() => {
    if (marketState.value === 'live') {
        const hh = String(nowKst.value.hour).padStart(2, '0');
        const mm = String(nowKst.value.minute).padStart(2, '0');
        return `장중 · ${hh}:${mm} 기준`;
    }
    const [, m, d] = selectedDate.value.split('-');
    return `종가 · ${m}/${d} 마감`;
});
const priceLabel = computed(() => (marketState.value === 'live' ? '현재가' : '종가'));

onMounted(async () => {
    clock = setInterval(() => { nowKst.value = kstNowParts(); }, 30 * 1000);
    document.addEventListener('click', onDocClick, true);
    document.addEventListener('keydown', onKeyDown);
    await getStockMainData();
    loadPriorityTarget();
});
onBeforeUnmount(() => {
    clearInterval(clock);
    document.removeEventListener('click', onDocClick, true);
    document.removeEventListener('keydown', onKeyDown);
});

const getStockMainData = async () => {
    isLoading.value = true;
    try {
        const searchParam = { 'ymd': selectedDate.value.replaceAll('-', '') };
        const { data } = await aibeesApi.get('/api/v1/stocks/buy-target', { params: searchParam });

        resultData.value = data.data.length == 0 ? [] : data.data;
    } catch (e) {
        console.error(e);
    }
    finally {
        isLoading.value = false;
    }
};

const handleDateChange = () => getStockMainData();
const openDatePicker = () => dateInput.value?.showPicker?.();

/* ── 날짜 ±1 이동 (주말은 건너뛴다: 금요일에서 +1 → 바로 월요일, 월요일에서 -1 → 바로 금요일) ── */
const stepSelectedDate = (deltaDays) => {
    const [y, m, d] = selectedDate.value.split('-').map(Number);
    let next = shiftDate(y, m, d, deltaDays);
    while (next.weekday === 0 || next.weekday === 6) {
        next = shiftDate(next.year, next.month, next.day, deltaDays > 0 ? 1 : -1);
    }
    selectedDate.value = toYmdString(next.year, next.month, next.day);
    getStockMainData();
};

/* ══════════════ 매수타겟 정렬 ══════════════ */
const SORT_OPTIONS = [
    { key: 'composite_rank_no', label: '종합 순위', dir: 'asc',  ascLabel: '높은 순위 먼저', descLabel: '낮은 순위 먼저' },
    { key: 'rank_no',     label: '추천순위',     dir: 'asc',  ascLabel: '높은 순위 먼저', descLabel: '낮은 순위 먼저' },
    { key: 'score',       label: '점수',         dir: 'desc', ascLabel: '낮은 점수 먼저', descLabel: '높은 점수 먼저' },
    { key: 'volume',      label: '거래량',       dir: 'desc', ascLabel: '적은 순',        descLabel: '많은 순' },
    { key: 'shape_proba', label: '급등패턴 순위', dir: 'desc', ascLabel: '낮은 확률 먼저', descLabel: '높은 확률 먼저' },
];

// 2026-09 세션 후속: watch 게이트와 병행하는 2단계(top10→모멘텀 재정렬) 방식이 실전
// 시뮬레이션에서 재현성 있게 우수해 기본 정렬을 composite_rank_no 로 승격.
const sortKey = ref('composite_rank_no');
const sortDir = ref('asc');

const currentSort = computed(
    () => SORT_OPTIONS.find(o => o.key === sortKey.value) ?? SORT_OPTIONS[0]);

// select 의 v-model 이 sortKey 를 이미 바꿔 놓은 뒤에 불린다. 정렬 기준이 바뀌면 방향을 그 기준의
// 기본값으로 되돌린다(예: 점수는 높은 순, 순위는 낮은 번호 먼저). 빼먹으면 "점수 ↑" 상태가
// 다른 기준으로 넘어가 의도와 반대로 정렬된다.
const onSortKeyChange = () => {
    sortDir.value = SORT_OPTIONS.find(o => o.key === sortKey.value)?.dir ?? 'desc';
};
const toggleSortDir = () => { sortDir.value = sortDir.value === 'desc' ? 'asc' : 'desc'; };

const sortNum = (v) => {
    if (v === null || v === undefined || v === '') return null;
    const n = Number(v);
    return Number.isNaN(n) ? null : n;
};

const sortedData = computed(() => {
    const key = sortKey.value;
    const desc = sortDir.value === 'desc';
    return [...resultData.value].sort((a, b) => {
        const va = sortNum(a[key]);
        const vb = sortNum(b[key]);
        if (va === null && vb === null) return 0;
        if (va === null) return 1;      // null 은 방향 무관 항상 뒤
        if (vb === null) return -1;
        if (va !== vb) return desc ? vb - va : va - vb;
        return String(a.stock_code ?? '').localeCompare(String(b.stock_code ?? ''));
    });
});

/* ── 목록: 홈은 상위 3개만 보여준다. 전체는 "자세히보기" → 매수추천 메뉴(/stock/buy-target) ── */
const HOME_COUNT = 3;
const goToBuyTarget = () => router.push({ path: '/stock/buy-target' });

const rows = computed(() =>
    sortedData.value.slice(0, HOME_COUNT).map(item => ({
        item,
        chg: changeInfo(item),
        reason: reasonLine(item),
    })));

// 정렬 기준·날짜가 바뀌면 처음 상태로. (최우선타겟은 서버 저장값이라 날짜를 넘나들어도 유지된다)
watch([sortKey, sortDir, selectedDate], () => {
    expandedCode.value = null;
});

/* ── 아코디언: 한 번에 하나만 펼침 ── */
const expandedCode = ref(null);
const toggleRow = (code) => { expandedCode.value = expandedCode.value === code ? null : code; };

/* ── 최우선타겟: 사용자가 매수추천 항목 중 하나를 직접 지정 ──
 * 서버(trade_buy_target_priority, 유저당 1건·날짜 무관 전역값)에 저장된다.
 * 다음 영업일 09:00 정규장 매수 라운드에서 worker(BuyExecutor1)가 이 값을 읽어
 * 그 날 매수타겟 1순위로 승격시키고, 라운드가 끝나면(매수 성공·스킵 무관) 1회성으로
 * 초기화한다 — 그래서 프론트도 "선택 즉시 서버에 반영"만 하고 별도 유효기간은 두지 않는다.
 */
const priorityTarget = ref(null);     // 현재 지정된 stock_code (없으면 null)
const priorityTargetName = ref('');   // 위 종목명 — 다른 날짜에서 지정된 경우 표시용
const sheetOpen = ref(false);

const priorityItem = computed(() =>
    priorityTarget.value ? sortedData.value.find(i => i.stock_code === priorityTarget.value) ?? null : null);

const loadPriorityTarget = async () => {
    if (!isLoggedIn.value) return;   // 게스트는 로그인 전용 API 를 부르지 않는다
    try {
        const { data } = await aibeesApi.get('/api/v1/stocks/buy-target/priority');
        priorityTarget.value = data?.data?.stock_code ?? null;
        priorityTargetName.value = data?.data?.stock_name ?? '';
    } catch (e) {
        // 조회가 안 돼도 화면 자체는 정상 동작해야 하므로 조용히 무시.
        priorityTarget.value = null;
        priorityTargetName.value = '';
    }
};

const selectPriority = async (code) => {
    sheetOpen.value = false;
    const prevCode = priorityTarget.value;
    const prevName = priorityTargetName.value;
    try {
        if (!code) {
            await aibeesApi.delete('/api/v1/stocks/buy-target/priority');
            priorityTarget.value = null;
            priorityTargetName.value = '';
            return;
        }
        // 서버가 "그 ymd 매수타겟 목록에 실제 존재하는 종목인지"를 검증하므로
        // 지금 화면에 표시 중인 기준일(selectedDate)을 함께 보낸다.
        const ymd = selectedDate.value.replaceAll('-', '');
        const { data } = await aibeesApi.put('/api/v1/stocks/buy-target/priority', { ymd, stock_code: code });
        priorityTarget.value = code;
        priorityTargetName.value = data?.data?.stock_name ?? '';
    } catch (e) {
        alert(e?.response?.data?.error?.message || '최우선타겟 저장에 실패했습니다.');
        priorityTarget.value = prevCode;   // 실패했으니 선택 상태를 되돌린다
        priorityTargetName.value = prevName;
    }
};

/* ── 간이차트 (최근 120영업일 봉차트 + 20/60/120일선) ──
 * 기본 숨김 — "차트" 버튼으로 종목별 개별 토글. ChartStock.vue(전체 차트 페이지)와
 * 동일한 CandlestickChart 컴포넌트·색상 배색을 재사용해 일관성을 맞춘다.
 */
const expandedCharts = ref(new Set());
const toggleChart = (code) => {
    const next = new Set(expandedCharts.value);
    next.has(code) ? next.delete(code) : next.add(code);
    expandedCharts.value = next;
};

const buyTargetCandleData = (item) => {
    const rows = item.chart_data || [];
    const toXY = (key) => rows.map(r => ({
        x: (r.date || '').slice(0, 10),
        y: r[key] != null ? Number(r[key]) : null,
    }));

    return {
        labels: rows.map(r => (r.date || '').slice(0, 10)),
        datasets: [
            {
                label: 'Candle',
                data: rows.map(r => ({
                    x: (r.date || '').slice(0, 10),
                    o: Number(r.open), h: Number(r.high), l: Number(r.low), c: Number(r.close),
                })),
                color: { up: '#c51300', down: '#03748d', unchanged: '#999999' },
            },
            { label: 'MA20',  data: toXY('ma20'),  borderColor: '#efa55b', type: 'line', pointRadius: 0 },
            { label: 'MA60',  data: toXY('ma60'),  borderColor: '#8bb400', type: 'line', pointRadius: 0 },
            { label: 'MA120', data: toXY('ma120'), borderColor: '#01b6f3', type: 'line', pointRadius: 0 },
        ],
    };
};

// 카드 내 미니 프리뷰용 — 줌/팬 비활성화, 범례는 커스텀 legend로 대체, 축은 최소화
const miniCandleOptions = {
    plugins: {
        legend: { display: false },
        zoom: {
            pan: { enabled: false },
            zoom: { wheel: { enabled: false }, pinch: { enabled: false } },
        },
    },
    scales: {
        // x축 display:false 를 바로 주면(Chart.js 3.9 + category 스케일) 범위(min/max) 계산 자체가
        // 깨져서 데이터가 거의 안 보이는 버그가 있다 — 축은 켜두고 눈금표시(ticks)만 숨긴다.
        x: { type: 'category', grid: { display: false }, ticks: { display: false } },
        y: { position: 'right', beginAtZero: false, ticks: { font: { size: 9 } } },
    },
};
</script>

<style scoped lang="scss">
// 양봉상회 디자인 토큰(목업 기준)
$bg:       #FFFBEA;
$bar:      #FFF4C2;
$card:     #FFFFFF;
$line:     #EFE2BC;
$line-2:   #EAD9A6;
$brown:    #7A4423;
$brown-d:  #4A2814;
$yellow:   #FFC20E;
$ink:      #2B1D14;
$sub:      #6B5B4E;
$sub-2:    #7A6B5D;
$up:       #D12B2B;
$down:     #1F5BD1;

#home {
    min-height: 100vh;
    background: $bg;
    color: $ink;
    text-align: left;
    font-family: 'Pretendard', 'IBM Plex Sans KR', -apple-system, 'Apple SD Gothic Neo', sans-serif;
    font-variant-numeric: tabular-nums;
}

/* ── 헤더 ── */
.home-header {
    background: $bar;
    // 모바일: 스크롤해도 상단에 붙는다. top 은 노치/상태바(env) 아래 — 상태바 영역 자체는
    // App.vue 의 고정 덮개가 불투명하게 가린다(콘텐츠가 상태바 뒤로 비치지 않게).
    position: sticky;
    top: env(safe-area-inset-top, 0px);
    z-index: 50;
}

.hh-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 4px 12px 8px 16px;
}

.brand-chip {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    height: 40px;
    padding: 0 12px 0 8px;
    border: 0;
    border-radius: 10px;
    background: $brown;
    box-shadow: 0 2px 0 $brown-d;
    cursor: pointer;

    .brand-logo { width: 26px; height: 26px; }
    .brand-name {
        font-family: 'Do Hyeon', 'Pretendard', sans-serif;
        font-size: 21px;
        color: $yellow;
        letter-spacing: .5px;
    }
}

.hh-actions { display: flex; align-items: center; gap: 2px; }

.icon-btn {
    width: 44px;
    height: 44px;
    border: 0;
    background: transparent;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    color: $brown;
    cursor: pointer;
}

.avatar {
    width: 32px;
    height: 32px;
    border-radius: 16px;
    background: $yellow;
    color: #5C3118;
    font-weight: 700;
    font-size: 14px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
}

.login-btn {
    min-height: 44px;
    padding: 0 12px;
    border: 0;
    background: transparent;
    color: $brown;
    font-size: 14px;
    font-weight: 700;
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
        font-size: 14px;
        color: $ink;
        cursor: pointer;
        &:hover { background: $bg; }
        &.danger { color: $up; }
    }
}

// 12px 차양 띠: 노랑 반원이 줄지어 늘어진다
.awning {
    height: 12px;
    background: radial-gradient(circle at 50% 0, #{$yellow} 9px, transparent 9.5px) repeat-x;
    background-size: 22px 12px;
    border-top: 3px solid $brown;
}

/* ── 본문 ── */
.home-main {
    max-width: 640px;
    margin: 0 auto;
    padding: 12px 16px 24px;
    display: flex;
    flex-direction: column;
    gap: 16px;
}

/* ── 날짜 네비게이터 ── */
.date-nav {
    display: flex;
    align-items: center;
    justify-content: space-between;
}

.nav-btn {
    width: 44px;
    height: 44px;
    border: 1px solid $line-2;
    border-radius: 12px;
    background: $card;
    color: $brown;
    font-size: 18px;
    cursor: pointer;
}

.date-center { position: relative; }
.date-btn {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2px;
    min-height: 44px;
    padding: 0 8px;
    border: 0;
    background: transparent;
    color: $ink;
    cursor: pointer;
}
.date-main { font-size: 17px; font-weight: 700; }
.date-status {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    color: $sub;

    .dot { width: 7px; height: 7px; border-radius: 4px; background: #9A8F84; }
    &.live .dot { background: #E07A00; }
}
.hidden-input {
    position: absolute;
    left: 50%;
    bottom: 0;
    width: 1px;
    height: 1px;
    opacity: 0;
    pointer-events: none;
}

/* ── 최우선 타겟 히어로 ── */
.priority-hero {
    background: $brown;
    border-radius: 18px;
    padding: 18px;
    color: #FFF8E1;
    display: flex;
    flex-direction: column;
    gap: 12px;
    box-shadow: 0 4px 0 $brown-d;

    .ph-top { display: flex; align-items: center; justify-content: space-between; }
    .ph-badge {
        background: $yellow;
        color: $brown-d;
        font-size: 12px;
        font-weight: 700;
        padding: 4px 10px;
        border-radius: 999px;
    }
    .ph-change {
        border: 0;
        background: transparent;
        color: #FFE7A0;
        font-size: 13px;
        min-height: 44px;
        padding: 0 4px;
        cursor: pointer;
    }

    .ph-body { display: flex; align-items: flex-end; justify-content: space-between; gap: 12px; }
    .ph-who { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
    .ph-name { font-size: 22px; font-weight: 700; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .ph-code { font-size: 13px; color: #E8D5B8; }
    .ph-px { display: flex; flex-direction: column; align-items: flex-end; gap: 2px; flex-shrink: 0; }
    .ph-price { font-size: 20px; font-weight: 700; }
    .ph-chg {
        font-size: 13px;
        font-weight: 600;
        &.up   { color: #FFB4A8; }
        &.down { color: #A9C4FF; }
        &.flat { color: #E8D5B8; }
    }

    .ph-reason {
        margin: 0;
        font-size: 14px;
        line-height: 1.5;
        color: #F5E6CC;
        background: rgba(0, 0, 0, .18);
        border-radius: 10px;
        padding: 10px 12px;
    }
    .ph-empty { margin: 0; font-size: 14px; line-height: 1.5; color: #F5E6CC; }
    .ph-skeleton { height: 96px; border-radius: 12px; background: rgba(255, 255, 255, .12); animation: pulse 1.6s infinite ease-in-out; }

    .ph-cta {
        min-height: 48px;
        border: 0;
        border-radius: 12px;
        background: $yellow;
        color: #3A200F;
        font-weight: 700;
        font-size: 15px;
        cursor: pointer;
    }
}

/* ── 리스트 헤더 ── */
.list-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 12px;

    h2 { margin: 0; font-size: 17px; font-weight: 700; }
    .count { color: #A0662F; }
}
.list-tools { display: flex; align-items: center; gap: 6px; }

.sort-pill {
    position: relative;
    display: inline-flex;
    align-items: center;
    min-height: 36px;
    padding: 0 14px;
    border: 1px solid $line-2;
    border-radius: 999px;
    background: $card;
    font-size: 13px;
    color: #4A3628;

    select {
        position: absolute;
        inset: 0;
        width: 100%;
        height: 100%;
        opacity: 0;
        cursor: pointer;
        font-size: 16px;   // iOS 포커스 확대 방지
    }
}
.dir-btn {
    width: 36px;
    height: 36px;
    border: 1px solid $line-2;
    border-radius: 999px;
    background: $card;
    color: #4A3628;
    font-size: 15px;
    cursor: pointer;
}

/* ── 컴팩트 리스트 ── */
.reco-list {
    background: $card;
    border: 1px solid $line;
    border-radius: 16px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
}
.reco-item { border-bottom: 1px solid #F3EAD2; }

.reco-row {
    width: 100%;
    border: 0;
    background: $card;
    padding: 14px;
    display: grid;
    grid-template-columns: 26px minmax(0, 1fr) auto;
    gap: 10px;
    align-items: start;
    text-align: left;
    cursor: pointer;
    color: $ink;
    font-family: inherit;

    &.open { background: #FFFDF5; }

    .rank { font-family: 'Do Hyeon', 'Pretendard', sans-serif; font-size: 18px; color: #A0662F; padding-top: 1px; }
    .who { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
    .name-line { display: flex; align-items: baseline; gap: 6px; min-width: 0; }
    .name { font-size: 16px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .code { font-size: 12px; color: $sub-2; flex-shrink: 0; }
    .pri-chip {
        flex-shrink: 0;
        padding: 1px 7px;
        border-radius: 999px;
        background: $yellow;
        color: $brown-d;
        font-size: 11px;
        font-weight: 700;
    }
    .reason { font-size: 13px; color: $sub; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .px { display: flex; flex-direction: column; align-items: flex-end; gap: 3px; }
    .price { font-size: 16px; font-weight: 700; }
}

// 등락: 색뿐 아니라 ▲/▼ 기호와 절대값을 함께 쓴다
.chg {
    font-size: 12px;
    font-weight: 600;
    white-space: nowrap;
    &.up   { color: $up; }
    &.down { color: $down; }
    &.flat { color: $sub; }
}

.reco-detail {
    padding: 4px 14px 16px 50px;
    display: flex;
    flex-direction: column;
    gap: 12px;
    background: #FFFDF5;
}

.score-line { font-size: 12px; color: $sub; b { color: $ink; } }

// 시/고/저/종 + 거래량 표
.ohlc {
    width: 100%;
    border-collapse: collapse;
    table-layout: fixed;
    background: $card;
    border: 1px solid $line;
    border-radius: 10px;
    overflow: hidden;

    th, td { padding: 8px 6px; text-align: right; font-size: 13px; border-bottom: 1px solid #F3EAD2; }
    thead th { font-size: 11px; font-weight: 600; color: $sub; background: #FFFDF5; }
    tbody td { font-weight: 600; }
    td.hi { color: $up; }
    td.lo { color: $down; }
    td.cl { color: $ink; font-weight: 700; }
    tr:last-child th, tr:last-child td { border-bottom: 0; }
    .vol th { font-size: 11px; font-weight: 600; color: $sub; text-align: left; padding-left: 10px; background: #FFFDF5; }
}

.rd-actions { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
.btn-outline {
    min-height: 44px;
    border-radius: 10px;
    border: 1px solid #E3D3A8;
    background: transparent;
    color: #4A3628;
    font-size: 14px;
    cursor: pointer;
    font-family: inherit;

    &.strong { border: 1.5px solid $brown; color: $brown; font-weight: 600; }
}

.more-btn {
    min-height: 48px;
    border: 0;
    background: #FFFDF5;
    color: $brown;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
}

.skeleton-row { height: 72px; border-bottom: 1px solid #F3EAD2; background: $card; animation: pulse 1.6s infinite ease-in-out; }
.empty-box { text-align: center; padding: 56px 0; color: $sub; font-size: 14px; }

.disclaimer { margin: 0; font-size: 11px; line-height: 1.5; color: $sub-2; text-align: center; }

/* ── 간이 차트 ── */
.mini-chart {
    width: 100%;
    box-sizing: border-box;

    .mini-chart-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 6px; }
    .mini-legend { display: flex; gap: 8px; flex-wrap: wrap; }
    .leg-item {
        font-size: 11px;
        font-weight: 600;
        color: $sub;
        display: flex;
        align-items: center;
        gap: 3px;
        &::before { content: ''; display: inline-block; width: 10px; height: 2px; background: var(--c); }
    }
    .mini-chart-detail {
        flex-shrink: 0;
        min-height: 32px;
        padding: 0 10px;
        border: 1px solid #E3D3A8;
        border-radius: 8px;
        background: $card;
        color: $brown;
        font-size: 12px;
        font-weight: 600;
        cursor: pointer;
        font-family: inherit;
    }
    .mini-chart-canvas { width: 100%; height: 220px; }
}

/* ── 최우선 타겟 선택 시트 ── */
.sheet-overlay {
    position: fixed;
    inset: 0;
    z-index: 3000;
    background: rgba(43, 29, 20, .45);
    display: flex;
    align-items: flex-end;
    justify-content: center;
}
.sheet {
    width: 100%;
    max-width: 640px;
    max-height: 72vh;
    display: flex;
    flex-direction: column;
    background: $card;
    border-radius: 18px 18px 0 0;
    padding-bottom: env(safe-area-inset-bottom, 0px);
    color: $ink;
    text-align: left;
}
.sheet-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 6px 8px 6px 18px;
    border-bottom: 1px solid $line;
    strong { font-size: 16px; }
}
.sheet-close { width: 44px; height: 44px; border: 0; background: transparent; color: $sub; font-size: 16px; cursor: pointer; }
.sheet-list { margin: 0; padding: 4px 8px 12px; list-style: none; overflow-y: auto; }
.sheet-item {
    width: 100%;
    min-height: 48px;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 0 10px;
    border: 0;
    border-radius: 10px;
    background: transparent;
    text-align: left;
    cursor: pointer;
    font-family: inherit;
    color: $ink;

    &.on { background: $bar; font-weight: 700; }
    .si-rank { font-family: 'Do Hyeon', 'Pretendard', sans-serif; font-size: 16px; color: #A0662F; width: 24px; }
    .si-name { flex: 1; min-width: 0; font-size: 15px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
        em { font-style: normal; font-size: 12px; color: $sub-2; margin-left: 4px; } }
    .si-chg { font-size: 12px; font-weight: 600; &.up { color: $up; } &.down { color: $down; } &.flat { color: $sub; } }
}
.sheet-enter-active, .sheet-leave-active { transition: opacity .18s ease; .sheet { transition: transform .22s ease; } }
.sheet-enter-from, .sheet-leave-to { opacity: 0; .sheet { transform: translateY(24px); } }

@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: .5; }
}

/* ── 데스크톱: 상단 내비(Lnb)가 브랜드를 보여주므로 로고 칩은 숨기고 헤더는 흐름에 둔다 ── */
@media (min-width: 640px) {
    .home-header { position: static; }
    .hh-row { justify-content: flex-end; }
    .brand-chip { display: none; }
    .home-main { max-width: 720px; padding-top: 20px; }
}
</style>
