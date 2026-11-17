<template>
    <div id="stock-buy-target">
        <BrandHeader :title="title" back="/menu" />

        <div class="contents">
            <section class="head-desc">
                <div class="head-actions">
                    <div class="date-picker-trigger" @click="openDatePicker">
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none"
                            stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect>
                            <line x1="16" y1="2" x2="16" y2="6"></line>
                            <line x1="8" y1="2" x2="8" y2="6"></line>
                            <line x1="3" y1="10" x2="21" y2="10"></line>
                        </svg>
                        <span class="date-value">{{ dateLabel }}</span>
                        <input type="date" ref="dateInput" class="hidden-input" v-model="selectedDate"
                            @change="handleDateChange" />
                    </div>
                </div>
            </section>

            <!-- ── 정렬 (홈과 동일: 기준 select + 방향 버튼) ── -->
            <div v-if="!isLoading && resultData.length > 0" class="list-head">
                <h2>추천 종목 <span class="count">{{ sortedData.length }}</span></h2>
                <div class="list-tools">
                    <button type="button" class="dir-btn" @click="toggleSortDir"
                        :aria-label="`정렬 방향: ${sortDir === 'desc' ? currentSort.descLabel : currentSort.ascLabel}`"
                        :title="sortDir === 'desc' ? currentSort.descLabel : currentSort.ascLabel">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"
                            :style="{ transform: sortDir === 'desc' ? 'rotate(180deg)' : 'none' }" aria-hidden="true"><path d="M12 19V5M6 11l6-6 6 6"></path></svg>
                    </button>
                </div>
            </div>
            <!-- 정렬 기준: 가로로 넘기는 칩(방향은 위 ↑ 버튼) -->
            <SortChips v-if="!isLoading && resultData.length > 0" v-model="sortKey" :options="SORT_OPTIONS" @change="onSortKeyChange" />

            <section class="buy-target reco">
                <!-- 열 머리글: 아래 윗줄과 같은 칸 나눔(종목 | 현재가 | 봉) -->
                <div v-if="!isLoading && sortedData.length" class="reco-cols" aria-hidden="true">
                    <span class="c-who"></span>
                    <span class="c-px">{{ priceLabel }}</span>
                    <span class="c-candle"></span>
                </div>

                <div v-if="!isLoading && sortedData.length" class="reco-list">
                    <div v-for="(r, idx) in rows" :key="r.item.stock_code ?? idx" class="reco-item">
                        <button type="button" class="reco-row" :class="{ open: expandedCode === r.item.stock_code }"
                            :aria-expanded="expandedCode === r.item.stock_code ? 'true' : 'false'"
                            @click="toggleRow(r.item.stock_code)">
                            <span class="who">
                                <span class="name-line">
                                    <span class="rank">{{ String(rankNumber(idx)).padStart(2, '0') }}</span>
                                    <span class="name">{{ r.item.stock_name }}</span>
                                    <span v-if="r.item.sector_name" class="sector">{{ r.item.sector_name }}</span>
                                </span>
                                <!-- 시가총액은 코드 옆에 짧게(펼치면 정확한 값·수급) -->
                                <span class="code">{{ r.item.stock_code }}<template v-if="r.capShort"> · {{ r.capShort }}</template></span>
                            </span>
                            <span class="px">
                                <span class="price">{{ formatNumber(r.item.close) }}</span>
                                <span class="chg" :class="r.chg.cls">
                                    <span class="chg-full">{{ r.chg.text }}</span>
                                    <span class="chg-short">{{ r.chgShort }}</span>
                                </span>
                            </span>
                            <!-- 최근 5개 봉(chart_data 마지막 5개, 맨 오른쪽 = 추천일). 차트 데이터가 없으면 그날 봉 1개 -->
                            <MiniCandles v-if="r.recentBars.length" class="candle" :bars="r.recentBars" />
                            <DayCandle v-else mini class="candle" :open="r.item.open" :high="r.item.high" :low="r.item.low"
                                :close="r.item.close" :close-label="priceLabel" />
                            <!-- 7개 조건: 윗줄 아래 전체 폭 한 줄로 "이름 + 충족/미달" (✓ 기호 대신 글자 — 가독성 피드백 2026-10-11) -->
                            <span class="conds" :aria-label="`조건 ${r.summary.pass}/${r.summary.total} 충족`">
                                <span v-for="c in r.summary.rows" :key="c.key" class="cond" :class="{ on: c.pass }">
                                    <span class="cond-name">{{ COND_NAMES[c.key] ?? c.head }}</span>
                                    <span class="cond-state">{{ c.pass ? '충족' : '미달' }}</span>
                                </span>
                            </span>
                            <!-- 펼침 안내: 누르면 아래에 수급·밸류·조건 상세가 열린다(줄 전체가 버튼) -->
                            <span class="more-hint" aria-hidden="true">
                                {{ expandedCode === r.item.stock_code ? '접기' : '상세보기' }}
                                <svg class="more-chev" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                                    stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9l6 6 6-6"></path></svg>
                            </span>
                        </button>

                        <div v-if="expandedCode === r.item.stock_code" class="reco-detail">
                            <!-- 수급·밸류 요약(펼침 맨 위): 조건 줄과 같은 칸 모양. 수급은 추천일 이하 최근 영업일, PER/PBR 은 추천일 배치 시점 -->
                            <div class="facts">
                                <span v-for="f in r.facts" :key="f.name" class="fact">
                                    <span class="cond-name">{{ f.name }}</span>
                                    <span class="fact-value" :class="f.cls">{{ f.value }}</span>
                                </span>
                            </div>
                            <!-- 시가총액 · 수급: 추천일 이하 가장 최근 영업일 기준. 순매수=빨강 / 순매도=파랑 -->
                            <div v-if="r.market" class="mk">
                                <div class="mk-head">
                                    <span class="mk-title">시가총액 · 수급</span>
                                    <span v-if="r.market.dateLabel" class="mk-date">{{ r.market.dateLabel }} 종가·순매수 기준</span>
                                </div>
                                <ul class="mk-list">
                                    <li v-if="r.item.market_cap != null" class="mk-row">
                                        <span class="mk-label">시가총액</span>
                                        <span class="mk-value">{{ formatEok(r.item.market_cap) }}</span>
                                    </li>
                                    <li v-for="f in r.market.flows" :key="f.label" class="mk-row">
                                        <span class="mk-label">{{ f.label }}</span>
                                        <span class="mk-value" :class="signClass(f.amt)">
                                            {{ formatNetAmt(f.amt) }}<span v-if="f.qty != null" class="mk-qty">{{ formatNetQty(f.qty) }}</span>
                                        </span>
                                    </li>
                                </ul>
                            </div>
                            <!-- 조건 목록(홈과 같은 모양): 거래량 두 줄은 실제 수치 -->
                            <ul class="cs-list">
                                <li v-for="c in r.summary.rows" :key="c.key" class="cs-row" :class="{ off: !c.pass }">
                                    <span class="cs-label">{{ detailLabel(c.label) }}</span>
                                    <span class="cs-value">{{ isStatusText(c.value) ? '' : c.value }}</span>
                                    <span class="cs-state">{{ c.pass ? '충족' : '미달' }}</span>
                                </li>
                            </ul>
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

                </div>

                <div v-else-if="isLoading" class="reco-list">
                    <div class="skeleton-row" v-for="n in 4" :key="n"></div>
                </div>

                <div v-else class="empty-box">
                    <p>분석된 데이터가 없습니다. 날짜를 변경해 보세요.</p>
                </div>
            </section>
        </div>
    </div>
</template>

<script setup>
import CandlestickChart from '../common/comp/CandlestickChart.vue';
import { buyTargetCandleData, miniCandleOptions } from '@scripts/miniCandle.js';
import aibeesApi from '@scripts/aibeesApi.js';
import { recoLevel } from '@scripts/useAccess.js';
import {
    numOrNull, formatNumber, hasValue, changeInfo, conditionSummary,
    kstNowParts, isMarketOpenNow, weekdayKo, toYmdString, getLatestBatchDate,
} from '@scripts/stockSignals.js';
import {
    formatEok, formatCapShort, formatNetAmt, formatNetAmtShort, formatNetQty, formatRatio, signClass, shortYmd,
} from '@scripts/marketFormat.js';

const router = useRouter();
const title = ref('매수추천');

const goToStockInfo = (stock_code, stock_name) => {
    // ymd: 상세 화면이 같은 날짜의 매수타겟 행(근거·재무·조건)을 찾는 데 쓴다.
    router.push({ path: '/stock/info', query: { stock_code, stock_name, ymd: selectedDate.value.replaceAll('-', '') } });
};
const goToChart = (stock_code) => {
    router.push({ path: '/stock/chart', query: { code: stock_code } });
};
const resultData = ref([]);
const isLoading = ref(true);

/* ── 기준일: 가장 최신 배치 데이터가 있는 날(KST) / 장중 여부는 홈과 같은 규칙 ── */
const nowKst = ref(kstNowParts());
let clock = null;
const selectedDate = ref(getLatestBatchDate());
const dateInput = ref(null);

const todayDash = computed(() => toYmdString(nowKst.value.year, nowKst.value.month, nowKst.value.day));
const marketState = computed(() =>
    selectedDate.value === todayDash.value && isMarketOpenNow(nowKst.value) ? 'live' : 'closed');
const priceLabel = computed(() => (marketState.value === 'live' ? '현재가' : '종가'));
const dateLabel = computed(() => {
    const [y, m, d] = selectedDate.value.split('-');
    return `${y}.${m}.${d} (${weekdayKo(selectedDate.value)})`;
});

onMounted(async () => {
    clock = setInterval(() => { nowKst.value = kstNowParts(); }, 30 * 1000);
    await getStockMainData();
});
onBeforeUnmount(() => clearInterval(clock));

const getStockMainData = async () => {
    isLoading.value = true;
    try {
        const searchParam = { 'ymd': selectedDate.value.replaceAll('-', '') };
        const { data } = await aibeesApi.get('/api/v1/stocks/buy-target', { params: searchParam });

        if (data.data.length == 0) {
            resultData.value = [];
        } else {
            resultData.value = data.data;
        }
    } catch (e) {
        console.error(e);
    }
    finally {
        isLoading.value = false;
    }
};

const handleDateChange = () => getStockMainData();
const openDatePicker = () => dateInput.value?.showPicker();

/* ══════════════ 매수타겟 정렬 ══════════════
 * 조회는 하루치 전체를 한 번에 받아오므로 클라이언트에서 정렬한다(재조회 없음).
 *
 * 규칙은 worker(trade_worker/repository.py _ORDER_FIELDS)와 맞춘다:
 *   · 필드별 기본 방향 — rank_no 는 작을수록 상위(asc), score/volume 은 클수록 상위(desc)
 *   · 값이 없는(null) 종목은 정렬 방향과 무관하게 항상 뒤
 *   · 전부 동점이면 stock_code 로 최종 결정 (매 조회마다 순서가 흔들리지 않도록)
 */
// 열람 가능한 최고 단계. 실전 = WORKER_USER 권한(운영자 부여), 고급 = RECO_ADVANCED 기능 플래그(광고·구독으로 부여 예정).
// 서버(/buy-target)가 같은 기준으로 권한 밖 정보를 응답에서 지운다 — 여기는 화면 구성용일 뿐 보안이 아니다.
const route = useRoute();
const userLevel = computed(() => {
    if (import.meta.env.DEV) {   // 개발 중 미리보기 전용(?level=1|2|3)
        const q = Number(route.query.level);
        if (q >= 1 && q <= 3) return q;
    }
    return recoLevel();
});

// 고급 단계 이상에서만 값이 내려오는 정렬 기준(기본 단계에는 서버가 이 필드를 주지 않는다)
const ADVANCED_SORT_KEYS = ['composite_rank_no', 'shape_proba', 'frgn_amt', 'orgn_amt'];
const SORT_ALL = [
    { key: 'composite_rank_no', label: '종합 순위(신규)', dir: 'asc',  ascLabel: '높은 순위 먼저', descLabel: '낮은 순위 먼저' },
    { key: 'rank_no',     label: '추천순위',     dir: 'asc',  ascLabel: '높은 순위 먼저', descLabel: '낮은 순위 먼저' },
    { key: 'score',       label: '점수',         dir: 'desc', ascLabel: '낮은 점수 먼저', descLabel: '높은 점수 먼저' },
    { key: 'volume',      label: '거래량',       dir: 'desc', ascLabel: '적은 순',        descLabel: '많은 순' },
    { key: 'shape_proba', label: '급등패턴 순위', dir: 'desc', ascLabel: '낮은 확률 먼저', descLabel: '높은 확률 먼저' },
    // 시가총액·수급(/buy-target 응답의 market_cap, frgn_amt, orgn_amt — StockService.attach_market_info)
    { key: 'market_cap',  label: '시가총액',     dir: 'desc', ascLabel: '작은 순',        descLabel: '큰 순' },
    { key: 'frgn_amt',    label: '외국인 순매수', dir: 'desc', ascLabel: '순매도 큰 순',   descLabel: '순매수 큰 순' },
    { key: 'orgn_amt',    label: '기관 순매수',   dir: 'desc', ascLabel: '순매도 큰 순',   descLabel: '순매수 큰 순' },
];
// 단계마다 알고리즘이 달라 쓸 수 있는 정렬 기준도 다르다.
//   기본 단계: 옛 알고리즘이 채우는 추천순위·점수 / 고급 단계: 2파 알고리즘의 종합순위·모델 확률·수급
const BASIC_ONLY_SORT_KEYS = ['rank_no', 'score'];
const SORT_OPTIONS = computed(() => (activeStage.value.rank >= 2
    ? SORT_ALL.filter(o => !BASIC_ONLY_SORT_KEYS.includes(o.key))
    : SORT_ALL.filter(o => !ADVANCED_SORT_KEYS.includes(o.key))));

// 2026-09 세션 후속: 2단계(top10→모멘텀 재정렬) 방식이 우수해 고급 단계 기본 정렬은 composite_rank_no. 기본 단계는 추천순위.
const sortKey = ref('rank_no');
const sortDir = ref('asc');

const currentSort = computed(
    () => SORT_OPTIONS.value.find(o => o.key === sortKey.value) ?? SORT_OPTIONS.value[0]);

// select 의 v-model 이 sortKey 를 이미 바꿔 놓은 뒤에 불린다. 기준을 바꾸면 그 필드의 기본 방향으로 되돌린다.
// (거래량을 고르고 '적은 순'이 남아 있으면 의도와 반대 결과가 나온다)
const onSortKeyChange = () => {
    sortDir.value = SORT_OPTIONS.value.find(o => o.key === sortKey.value)?.dir ?? 'desc';
};
const toggleSortDir = () => { sortDir.value = sortDir.value === 'desc' ? 'asc' : 'desc'; };

// 카드 번호: 정렬 기준의 "기본 방향"일 때만 1위부터 매기고, 방향을 뒤집으면
// 목록을 새로 매기는 게 아니라 같은 순위를 거꾸로 보여준다(마지막 번호부터 역순).
const rankNumber = (index) => (
    sortDir.value === currentSort.value.dir ? index + 1 : sortedData.value.length - index
);

const sortNum = (v) => {
    if (v === null || v === undefined || v === '') return null;
    const n = Number(v);
    return Number.isNaN(n) ? null : n;
};

/* ══════════════ 추천 목록(단계 탭 없음) ══════════════
 * 비밀상회는 기본/고급/실전 탭을 나누지 않고 '매수추천' 목록 하나만 보여준다(2026-11-17).
 * 목록 = 사용자가 볼 수 있는 단계 중 가장 높은 단계(실전은 아직 준비 중이라 고급까지) — 홈(Home.vue)과 같은 규칙.
 * 서버(RecoLevel.py)가 행마다 reco_stages 를 주고, 권한 밖 종목·정보는 응답에서 지운다.
 */
const STAGE_RANK = computed(() => Math.min(userLevel.value, 2));
const activeStage = computed(() => ({ rank: STAGE_RANK.value }));
const stageItems = (rank) => resultData.value.filter(it => (it.reco_stages ?? [1]).includes(rank));
watch(STAGE_RANK, (r) => {
    sortKey.value = r >= 2 ? 'composite_rank_no' : 'rank_no';
    sortDir.value = 'asc';
}, { immediate: true });

const sortedData = computed(() => {
    const key = sortKey.value;
    const desc = sortDir.value === 'desc';
    const base = stageItems(activeStage.value.rank);
    return base.sort((a, b) => {
        const va = sortNum(a[key]);
        const vb = sortNum(b[key]);
        if (va === null && vb === null) return 0;
        if (va === null) return 1;      // null 은 방향 무관 항상 뒤
        if (vb === null) return -1;
        if (va !== vb) return desc ? vb - va : va - vb;
        return String(a.stock_code ?? '').localeCompare(String(b.stock_code ?? ''));
    });
});

// 좁은 화면용 등락: 기호 + 퍼센트만(절대값은 PC 폭에서만 보인다)
const shortChange = (chg) => {
    if (chg.pct === null) return '';
    const mark = chg.dir > 0 ? '▲' : (chg.dir < 0 ? '▼' : '–');
    return `${mark}${Math.abs(chg.pct).toFixed(2)}%`;
};

// 펼침 영역 '시가총액 · 수급' — 값이 하나도 없으면(수급 배치 전 등) 블록을 숨긴다
const marketInfo = (item) => {
    const flows = [
        { label: '외국인', amt: item.frgn_amt, qty: item.frgn_qty },
        { label: '기관',   amt: item.orgn_amt, qty: item.orgn_qty },
        { label: '개인',   amt: item.prsn_amt, qty: item.prsn_qty },
    ].filter(f => f.amt != null);
    if (item.market_cap == null && !flows.length) return null;
    return { flows, dateLabel: shortYmd(item.investor_ymd) };
};

// 목록 줄 오른쪽 미니 봉 개수 — chart_data(최근 120영업일)의 마지막 N개. 마지막 봉 = 추천일 봉
const RECENT_BARS = 5;

// 목록 줄 조건 이름 — 열 머리글 줄임말(거래/급증/BB …)보다 알아보기 쉬운 이름. 키는 conditionSummary rows.key
const COND_NAMES = {
    '거래제한': '거래량', '거래급등': '거래급증', 'MACD 크로스': 'MACD', 'OBV 크로스': 'OBV',
    'BB중심돌파': 'BB돌파', 'BB상단아래': '비과열', '중심선위': '20일선',
};
// conditionSummary 의 value 는 거래량 두 줄만 실제 수치, 나머지는 '충족'/'미충족' 문구 — 상태 칸과 겹치므로 숨긴다
const isStatusText = (v) => v === '충족' || v === '미충족';
// 상세 라벨 "거래량 기준 충족" 처럼 끝에 '충족'이 붙은 이름은 상태 칸(충족/미달)과 겹쳐 떼어 낸다
const detailLabel = (label) => String(label ?? '').replace(/\s*충족$/, '');

const rows = computed(() =>
    sortedData.value.map(item => {
        const chg = changeInfo(item);
        return {
            item, chg, chgShort: shortChange(chg), summary: conditionSummary(item),
            capShort: formatCapShort(item.market_cap), market: marketInfo(item),
            recentBars: (item.chart_data || []).slice(-RECENT_BARS),
            facts: [
                // 수급은 고급 정보 — 기본 단계는 서버가 값을 주지 않으므로 칸도 그리지 않는다
                ...(userLevel.value >= 2 && activeStage.value.rank >= 2 ? [
                    { name: '외국인', value: formatNetAmtShort(item.frgn_amt), cls: signClass(item.frgn_amt) },
                    { name: '기관',   value: formatNetAmtShort(item.orgn_amt), cls: signClass(item.orgn_amt) },
                ] : []),
                { name: 'PER',    value: formatRatio(item.per, { lossLabel: '적자' }), cls: '' },
                { name: 'PBR',    value: formatRatio(item.pbr), cls: '' },
            ],
        };
    }));

/* ── 아코디언: 한 번에 하나만 펼침 ── */
const expandedCode = ref(null);
const toggleRow = (code) => { expandedCode.value = expandedCode.value === code ? null : code; };
watch([sortKey, sortDir, selectedDate], () => { expandedCode.value = null; });

/* ── 매수타겟 카드 간이차트 (최근 120영업일 봉차트 + 5/20/60/120일선) ──
 * 기본 숨김 — "차트보기" 버튼으로 종목별 개별 토글. ChartStock.vue(전체 차트 페이지)와
 * 동일한 CandlestickChart 컴포넌트·색상 배색을 재사용해 일관성을 맞춘다.
 */
const expandedCharts = ref(new Set());
const toggleChart = (code) => {
    const next = new Set(expandedCharts.value);
    next.has(code) ? next.delete(code) : next.add(code);
    expandedCharts.value = next;
};

</script>

<style scoped lang="scss">
// 양봉상회 디자인 토큰 (홈과 동일)

#stock-buy-target {
    min-height: 100vh;
    background: var(--sc-surface);
    color: var(--sc-text);
    text-align: left;
    font-family: 'Pretendard', 'IBM Plex Sans KR', -apple-system, 'Apple SD Gothic Neo', sans-serif;
    font-variant-numeric: tabular-nums;
}

.contents {
    max-width: 720px;
    margin: 0 auto;
    padding: 16px 16px 24px;
}

.head-desc { display: flex; margin-bottom: 12px; }

/* ── Head Actions ── */
.head-actions {
    display: flex;
    align-items: center;
    gap: 10px;

    @media (max-width: 600px) {
        width: 100%;
    }
}

/* ── Date Picker ── */
.date-picker-trigger {
    position: relative;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 0 14px;
    min-height: 44px;
    border-radius: 14px;
    border: 1px solid var(--sc-border-strong);
    background: var(--sc-surface);
    color: var(--sc-point-ink);
    font-size: 0.88rem;
    font-weight: 600;
    cursor: pointer;
    transition: border-color .15s;

    &:hover { border-color: var(--sc-point); }

    .date-value { color: var(--sc-point-ink); }

    .hidden-input {
        position: absolute;
        opacity: 0;
        width: 0;
        height: 0;
    }
}

/* ── 정렬 (홈과 동일) ── */
.list-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 12px;

    h2 { margin: 0; font-size: 18px; font-weight: 700; }
    .count { color: var(--sc-point-ink); }
}
.list-tools { display: flex; align-items: center; gap: 4px; }
.dir-btn {
    width: 40px;
    height: 40px;
    border: 0;
    border-radius: 20px;
    background: var(--sc-border);
    color: var(--sc-point-ink);
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    justify-content: center;
}

/* ── 컴팩트 리스트: 카드 없이 페이지 배경 위에 구분선으로만 나열 (홈과 동일) ── */
.reco-list {
    border-top: 1px solid var(--sc-border);
    display: flex;
    flex-direction: column;
}
.reco-item { border-bottom: 1px solid var(--sc-border); }

/* 줄 칸 나눔: 윗줄 = 종목 | 현재가 | 작은 봉, 아랫줄 = 7개 조건(전체 폭). 머리글(.reco-cols)은 윗줄과 같은 값. */
.reco {
    --px-w: 96px;            // 현재가 칸(좁은 화면: 등락은 퍼센트만)
    --candle-w: 35px;        // 미니 봉 5개(MiniCandles: 봉 4px, 간격 7px)
    --gap: 10px;
    @media (min-width: 640px) {
        --px-w: 132px;       // 넓은 화면: 등락 절대값까지
        --gap: 14px;
    }
}
.reco-row, .reco-cols {
    display: grid;
    grid-template-columns: minmax(0, 1fr) var(--px-w) var(--candle-w);
    column-gap: var(--gap);
    align-items: center;
}

.reco-cols {
    padding: 0 0 6px;
    font-size: 9px;
    font-weight: 600;
    color: var(--sc-text-sub);
    .c-px { text-align: right; }
    @media (min-width: 640px) { font-size: 12px; }
}

.reco-row {
    width: 100%;
    border: 0;
    background: transparent;
    padding: 14px 0;
    text-align: left;
    cursor: pointer;
    color: var(--sc-text);
    font-family: inherit;

    .rank { font-family: 'Do Hyeon', 'Pretendard', sans-serif; font-size: 17px; line-height: 1; color: var(--sc-point-ink); flex-shrink: 0; }
    .who { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
    .name-line { display: flex; align-items: baseline; gap: 5px; min-width: 0; }    // 순위는 종목명 줄 안에
    // 좁은 칸이라 자르지 않고 최대 두 줄로 감싼다(한글 종목명은 띄어쓰기가 없어 글자 단위로 넘긴다)
    .name {
        font-size: 14px;
        font-weight: 600;
        line-height: 1.3;
        letter-spacing: -.2px;
        min-width: 0;
        overflow-wrap: anywhere;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
    }
    .code { font-size: 11px; color: var(--sc-text-sub); }
    .sector { font-size: 11px; color: var(--sc-text-sub); white-space: nowrap; flex-shrink: 0; }   // 업종(지수업종 중분류)

    // 7개 조건 — 윗줄 아래 전체 폭, 항상 7칸 1줄. 칸마다 이름 위 / 상태 아래, 칸 사이 옅은 세로선
    .conds {
        grid-column: 1 / -1;
        display: grid;
        grid-template-columns: repeat(7, minmax(0, 1fr));
        margin-top: 10px;
    }
    .cond {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 3px;
        min-width: 0;
        padding: 2px 0;
        line-height: 1.2;
        text-align: center;
        & + .cond { border-left: 1px solid var(--sc-border); }                    // 칸 사이 옅은 구분선
    }
    .cond-name {
        max-width: 100%;
        font-size: 11px;
        letter-spacing: -.3px;
        color: var(--sc-text-sub);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        @media (max-width: 359px) { font-size: 10px; letter-spacing: -.5px; }
    }
    // 펼침 안내 — 조건 줄 아래 오른쪽. 펼치면 '접기' + 화살표 뒤집힘
    .more-hint {
        grid-column: 1 / -1;
        justify-self: end;
        display: inline-flex;
        align-items: center;
        gap: 3px;
        margin-top: 8px;
        font-size: 12px;
        font-weight: 600;
        color: var(--sc-point-ink);
    }
    .more-chev { transition: transform .15s ease; }
    &.open .more-chev { transform: rotate(180deg); }
    .cond-state { font-size: 13px; font-weight: 400; color: var(--sc-text-mute); }    // 미달: 회색 보통
    .cond.on .cond-state { color: var(--sc-up); font-weight: 700; }               // 충족: 빨강 볼드

    .px { display: flex; flex-direction: column; align-items: flex-end; gap: 3px; min-width: 0; }
    .price { font-size: 15px; font-weight: 700; }
    .candle { justify-self: end; }
}

// 등락: 색뿐 아니라 ▲/▼ 기호를 함께 쓴다(넓은 화면은 절대값까지)
.chg {
    font-size: 12px;
    font-weight: 600;
    white-space: nowrap;
    .chg-full { display: none; }
    @media (min-width: 640px) {
        font-size: 13px;
        .chg-full { display: inline; }
        .chg-short { display: none; }
    }
    &.up   { color: var(--sc-up); }
    &.down { color: var(--sc-down); }
    &.flat { color: var(--sc-text-sub); }
}

.reco-detail {
    padding: 0 0 16px;
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.score-line { font-size: 12px; color: var(--sc-text-sub); b { color: var(--sc-text); } }

// 수급·밸류 요약 — 펼침 영역 맨 위. 조건 줄과 같은 칸 모양(4칸), 아래쪽에 옅은 가로선
.facts {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    padding-bottom: 10px;
    border-bottom: 1px solid var(--sc-border);
}
.fact {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 3px;
    min-width: 0;
    padding: 2px 0;
    line-height: 1.2;
    & + .fact { border-left: 1px solid var(--sc-border); }
}
.fact-value {
    max-width: 100%;
    font-size: 13px;
    font-weight: 600;
    color: var(--sc-text);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    &.up   { color: var(--sc-up); }      // 순매수
    &.down { color: var(--sc-down); }    // 순매도
}
.facts .cond-name { font-size: 11px; letter-spacing: -.3px; color: var(--sc-text-sub); white-space: nowrap; }

// 시가총액 · 수급 — 조건 목록과 같은 줄 리스트(카드·칩 없음). 등락은 글자색으로만
.mk {
    .mk-head {
        display: flex;
        align-items: baseline;
        justify-content: space-between;
        gap: 8px;
        padding-bottom: 6px;
    }
    .mk-title { font-size: 13px; font-weight: 700; color: var(--sc-text); }
    .mk-date  { font-size: 11px; color: var(--sc-text-sub); }
}
.mk-list { margin: 0; padding: 0; list-style: none; border-top: 1px solid var(--sc-border); }
.mk-row {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 12px;
    padding: 9px 0;
    border-bottom: 1px solid var(--sc-border);
    font-size: 13px;

    .mk-label { color: var(--sc-text-sub); white-space: nowrap; }
    .mk-value {
        font-weight: 600;
        color: var(--sc-text);
        text-align: right;
        white-space: nowrap;
        &.up   { color: var(--sc-up); }
        &.down { color: var(--sc-down); }
    }
    .mk-qty { margin-left: 6px; font-size: 11px; font-weight: 400; color: var(--sc-text-sub); }
}

// 조건 목록 (홈과 같은 모양)
.cs-list { margin: 0; padding: 0; list-style: none; border-top: 1px solid var(--sc-border); }
.cs-row {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) auto;
    align-items: baseline;
    column-gap: 10px;
    padding: 9px 0;
    border-bottom: 1px solid var(--sc-border);
    font-size: 13px;

    .cs-state { font-weight: 700; color: var(--sc-up); white-space: nowrap; }      // 충족: 빨강 볼드
    .cs-label { font-weight: 600; color: var(--sc-text); white-space: nowrap; }
    .cs-value {
        justify-self: end;
        text-align: right;
        font-size: 12px;
        color: var(--sc-text);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        max-width: 100%;
    }
    &.off { .cs-label, .cs-value { color: var(--sc-text-sub); font-weight: 400; } .cs-state { color: var(--sc-text-mute); font-weight: 400; } }
}

.rd-actions { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
.btn-outline {
    min-height: 44px;
    border-radius: 10px;
    border: 1px solid var(--sc-border-strong);
    background: transparent;
    color: var(--sc-text);
    font-size: 14px;
    cursor: pointer;
    font-family: inherit;

    &.strong { border: 1.5px solid var(--sc-point); color: var(--sc-point-ink); font-weight: 600; }
}

.more-btn {
    min-height: 52px;
    border: 0;
    background: transparent;
    color: var(--sc-point-ink);
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
}

.skeleton-row { height: 72px; border-bottom: 1px solid var(--sc-border); background: color-mix(in srgb, var(--sc-border) 35%, transparent); animation: pulse 1.6s infinite ease-in-out; }
.empty-box { text-align: center; padding: 56px 0; color: var(--sc-text-sub); font-size: 14px; }

/* ── 간이 차트 ── */
.mini-chart {
    width: 100%;
    box-sizing: border-box;

    .mini-chart-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 6px; }
    .mini-legend { display: flex; gap: 8px; flex-wrap: wrap; }
    .leg-item {
        font-size: 11px;
        font-weight: 600;
        color: var(--sc-text-sub);
        display: flex;
        align-items: center;
        gap: 3px;
        &::before { content: ''; display: inline-block; width: 10px; height: 2px; background: var(--c); }
    }
    .mini-chart-detail {
        flex-shrink: 0;
        min-height: 32px;
        padding: 0 10px;
        border: 1px solid var(--sc-border-strong);
        border-radius: 8px;
        background: var(--sc-surface);
        color: var(--sc-point-ink);
        font-size: 12px;
        font-weight: 600;
        cursor: pointer;
        font-family: inherit;
    }
    .mini-chart-canvas { width: 100%; height: 220px; }
}

@keyframes pulse {
    0%, 100% { opacity: .5; }
    50%       { opacity: .9; }
}
</style>
