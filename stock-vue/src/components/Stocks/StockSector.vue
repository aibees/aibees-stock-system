<template>
    <div id="stock-sector">
        <BrandHeader :title="title" back="/menu" />

        <div class="contents">
            <!-- 시장 선택: 글자 탭(밑줄) -->
            <div class="market-tabs" role="tablist">
                <button v-for="m in MARKETS" :key="m" type="button" role="tab" class="market-tab"
                    :class="{ on: market === m }" :aria-selected="market === m ? 'true' : 'false'"
                    @click="selectMarket(m)">{{ m === 'KOSPI' ? '코스피' : '코스닥' }}</button>
                <span v-if="basisLabel" class="basis">{{ basisLabel }}</span>
            </div>

            <div v-if="!isLoading && marketSectors.length" class="list-head">
                <h2>업종 <span class="count">{{ marketSectors.length }}</span></h2>
            </div>

            <section class="sector">
                <!-- 열 머리글 = 정렬 버튼 (누른 열 기준, 다시 누르면 방향 반전) -->
                <div v-if="!isLoading && marketSectors.length" class="sector-cols">
                    <span class="c-name"></span>
                    <button v-for="c in SORT_COLS" :key="c.key" type="button" class="col-sort"
                        :class="{ on: sortKey === c.key }" @click="toggleSort(c.key)">
                        {{ c.label }}<span v-if="sortKey === c.key" class="dir">{{ sortDir === 'desc' ? '↓' : '↑' }}</span>
                    </button>
                </div>

                <div v-if="!isLoading && marketSectors.length" class="sector-list">
                    <div v-for="s in sortedSectors" :key="s.sector_cd" class="sector-item">
                        <button type="button" class="sector-row" :class="{ open: openCd === s.sector_cd }"
                            :aria-expanded="openCd === s.sector_cd ? 'true' : 'false'" @click="toggleSector(s)">
                            <span class="who">
                                <span class="name-line">
                                    <span class="name">{{ s.sector_name }}</span>
                                    <span v-if="s.parent_name" class="parent">{{ s.parent_name }}</span>
                                </span>
                                <span class="sub">
                                    {{ s.stock_count }}종목 · <span class="up">상승 {{ s.up_count }}</span>
                                    · <span class="down">하락 {{ s.down_count }}</span>
                                </span>
                            </span>
                            <span class="v chg" :class="signClass(s.chg_rate)">{{ formatRate(s.chg_rate) }}</span>
                            <span class="v flow" :class="signClass(s.frgn_amt)">{{ formatNetAmtShort(s.frgn_amt) }}</span>
                            <span class="v flow" :class="signClass(s.orgn_amt)">{{ formatNetAmtShort(s.orgn_amt) }}</span>
                        </button>

                        <div v-if="openCd === s.sector_cd" class="sector-detail">
                            <div class="facts">
                                <span class="fact">
                                    <span class="fact-name">시가총액</span>
                                    <span class="fact-value">{{ s.market_cap ? formatCapShort(s.market_cap) : '–' }}</span>
                                </span>
                                <span class="fact">
                                    <span class="fact-name">외국인</span>
                                    <span class="fact-value" :class="signClass(s.frgn_amt)">{{ formatNetAmtShort(s.frgn_amt) }}</span>
                                </span>
                                <span class="fact">
                                    <span class="fact-name">기관</span>
                                    <span class="fact-value" :class="signClass(s.orgn_amt)">{{ formatNetAmtShort(s.orgn_amt) }}</span>
                                </span>
                                <span class="fact">
                                    <span class="fact-name">개인</span>
                                    <span class="fact-value" :class="signClass(s.prsn_amt)">{{ formatNetAmtShort(s.prsn_amt) }}</span>
                                </span>
                            </div>

                            <p v-if="detailLoading" class="state">불러오는 중…</p>
                            <p v-else-if="!detailStocks.length" class="state">종목을 불러오지 못했습니다.</p>
                            <ul v-else class="st-list">
                                <li v-for="(st, i) in visibleStocks" :key="st.stock_code">
                                    <button type="button" class="st-row" @click="goToStockInfo(st)">
                                        <span class="who">
                                            <span class="name-line">
                                                <span class="rank">{{ String(i + 1).padStart(2, '0') }}</span>
                                                <span class="name">{{ st.stock_name }}</span>
                                            </span>
                                            <span class="code">{{ st.stock_code }}<template v-if="st.market_cap"> · {{ formatCapShort(st.market_cap) }}</template></span>
                                        </span>
                                        <span class="px">
                                            <span class="price">{{ st.close != null ? formatNumber(st.close) : '–' }}</span>
                                            <span class="chg-sm" :class="signClass(st.chg_rate)">{{ formatRate(st.chg_rate) }}</span>
                                        </span>
                                    </button>
                                </li>
                            </ul>
                            <button v-if="detailStocks.length > visibleStocks.length" type="button" class="more"
                                @click="showAll = true">{{ detailStocks.length - visibleStocks.length }}종목 더 보기</button>
                        </div>
                    </div>
                </div>

                <p v-else-if="isLoading" class="state">불러오는 중…</p>
                <p v-else class="state">업종 데이터가 없습니다.</p>
            </section>
        </div>
    </div>
</template>

<script setup>
/**
 * 업종 — 테마 화면 대체. KRX 지수업종(중분류 우선, 없으면 대분류)별 전일 등락률·순매수.
 *   목록 : GET /api/v1/stocks/sectors                    (시장별 업종 요약, 등락률 = 시가총액 가중)
 *   펼침 : GET /api/v1/stocks/sectors/<market>/<cd>      (업종 내 종목, 시가총액 큰 순)
 * 서버 단위: 시가총액 = 억원, 순매수 = 백만원 (marketFormat.js 와 같음).
 */
import aibeesApi from '@scripts/aibeesApi.js';
import { formatNumber } from '@scripts/stockSignals.js';
import { formatCapShort, formatNetAmtShort, signClass, shortYmd } from '@scripts/marketFormat.js';

const router = useRouter();
const title = ref('업종');

const MARKETS = ['KOSPI', 'KOSDAQ'];
const SORT_COLS = [
    { key: 'chg_rate', label: '등락률' },
    { key: 'frgn_amt', label: '외국인' },
    { key: 'orgn_amt', label: '기관' },
];
const STOCK_PAGE = 20;
const UNCLASSIFIED_CD = '0000';

const market = ref('KOSPI');
const sectors = ref([]);
const ymd = ref(null);
const isLoading = ref(true);

const sortKey = ref('chg_rate');
const sortDir = ref('desc');

const openCd = ref(null);
const detailStocks = ref([]);
const detailLoading = ref(false);
const showAll = ref(false);

const basisLabel = computed(() => (ymd.value ? `${shortYmd(ymd.value)} 종가 · 전일 대비` : ''));
const marketSectors = computed(() => sectors.value.filter(s => s.market === market.value));

// 값 없는 업종과 '미분류'는 정렬과 무관하게 항상 뒤
const sortedSectors = computed(() => {
    const sign = sortDir.value === 'desc' ? -1 : 1;
    return [...marketSectors.value].sort((a, b) => {
        const ua = a.sector_cd === UNCLASSIFIED_CD, ub = b.sector_cd === UNCLASSIFIED_CD;
        if (ua !== ub) return ua ? 1 : -1;
        const va = a[sortKey.value], vb = b[sortKey.value];
        if (va == null || vb == null) return va == null ? (vb == null ? 0 : 1) : -1;
        return (va - vb) * sign || a.sector_name.localeCompare(b.sector_name);
    });
});

const visibleStocks = computed(() => (showAll.value ? detailStocks.value : detailStocks.value.slice(0, STOCK_PAGE)));

const getSectors = async () => {
    isLoading.value = true;
    try {
        const { data } = await aibeesApi.get('/api/v1/stocks/sectors');
        sectors.value = data.data?.sectors ?? [];
        ymd.value = data.data?.ymd ?? null;
    } catch (e) {
        console.error(e);
        sectors.value = [];
    } finally {
        isLoading.value = false;
    }
};

const selectMarket = (m) => {
    market.value = m;
    openCd.value = null;
};

const toggleSort = (key) => {
    if (sortKey.value === key) sortDir.value = sortDir.value === 'desc' ? 'asc' : 'desc';
    else { sortKey.value = key; sortDir.value = 'desc'; }
};

const toggleSector = async (s) => {
    if (openCd.value === s.sector_cd) { openCd.value = null; return; }
    openCd.value = s.sector_cd;
    showAll.value = false;
    detailStocks.value = [];
    detailLoading.value = true;
    try {
        const { data } = await aibeesApi.get(`/api/v1/stocks/sectors/${s.market}/${s.sector_cd}`,
            { params: ymd.value ? { ymd: ymd.value } : {} });
        // 응답이 늦게 와서 그 사이 다른 업종을 펼쳤으면 버린다
        if (openCd.value === s.sector_cd) detailStocks.value = data.data?.sector?.stocks ?? [];
    } catch (e) {
        console.error(e);
    } finally {
        if (openCd.value === s.sector_cd) detailLoading.value = false;
    }
};

const goToStockInfo = (st) => {
    router.push({ path: '/stock/info', query: { stock_code: st.stock_code, stock_name: st.stock_name } });
};

const formatRate = (v) => (v == null ? '–' : `${v > 0 ? '+' : v < 0 ? '−' : ''}${Math.abs(v).toFixed(2)}%`);

onMounted(getSectors);
</script>

<style scoped lang="scss">
// 양봉상회 디자인 토큰 (매수추천과 동일)
$card:  #FFFFFF;
$line:  #EFE2BC;
$line-soft: #F3EAD2;
$brown: #7A4423;
$ink:   #2B1D14;
$sub:   #6B5B4E;
$sub-2: #7A6B5D;
$up:    #C8282A;
$down:  #1F5BD1;
$amber: #A0662F;

#stock-sector {
    min-height: 100vh;
    background: $card;
    color: $ink;
    text-align: left;
    font-family: 'Pretendard', 'IBM Plex Sans KR', -apple-system, 'Apple SD Gothic Neo', sans-serif;
    font-variant-numeric: tabular-nums;
}

.contents {
    max-width: 720px;
    margin: 0 auto;
    padding: 16px 16px 24px;
}

.up   { color: $up; }
.down { color: $down; }

/* ── 시장 탭: 글자 + 밑줄 ── */
.market-tabs {
    display: flex;
    align-items: flex-end;
    gap: 18px;
    border-bottom: 1px solid $line;
    margin-bottom: 16px;
}
.market-tab {
    border: 0;
    background: transparent;
    padding: 8px 0 10px;
    margin-bottom: -1px;
    font: inherit;
    font-size: 16px;
    font-weight: 600;
    color: $sub-2;
    cursor: pointer;
    border-bottom: 2px solid transparent;
    &.on { color: $ink; font-weight: 700; border-bottom-color: $brown; }
}
.basis {
    margin-left: auto;
    padding-bottom: 11px;
    font-size: 12px;
    color: $sub-2;
}

.list-head {
    margin-bottom: 12px;
    h2 { margin: 0; font-size: 18px; font-weight: 700; }
    .count { color: $amber; }
}

/* ── 업종 목록: 카드 없이 구분선 ── */
.sector {
    --v-w: 64px;
    --gap: 8px;
    @media (min-width: 640px) { --v-w: 84px; --gap: 14px; }
}
.sector-cols, .sector-row {
    display: grid;
    grid-template-columns: minmax(0, 1fr) repeat(3, var(--v-w));
    column-gap: var(--gap);
    align-items: center;
}
.sector-cols { padding: 0 0 6px; }
.col-sort {
    border: 0;
    background: transparent;
    padding: 4px 0;
    font: inherit;
    font-size: 12px;
    font-weight: 600;
    color: $sub;
    text-align: right;
    cursor: pointer;
    white-space: nowrap;
    &.on { color: $brown; font-weight: 700; }
    .dir { margin-left: 2px; }
}

.sector-list { border-top: 1px solid $line; }
.sector-item { border-bottom: 1px solid $line; }

.sector-row {
    width: 100%;
    border: 0;
    background: transparent;
    padding: 14px 0;
    text-align: left;
    cursor: pointer;
    color: $ink;
    font-family: inherit;

    .who { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
    .name-line { display: flex; align-items: baseline; gap: 6px; min-width: 0; }
    .name { font-size: 15px; font-weight: 700; letter-spacing: -.2px; overflow-wrap: anywhere; }
    .parent { font-size: 11px; color: $sub-2; white-space: nowrap; }
    .sub { font-size: 11px; color: $sub-2; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

    .v { text-align: right; white-space: nowrap; font-weight: 600; }
    .chg { font-size: 15px; font-weight: 700; }
    .flow { font-size: 12px; }
    .v:not(.up):not(.down) { color: $sub; }
}

.sector-detail { padding: 0 0 16px; }

// 업종 합계 — 매수추천 펼침의 .facts 와 같은 4칸
.facts {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    padding-bottom: 10px;
    border-bottom: 1px solid $line-soft;
}
.fact {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 3px;
    min-width: 0;
    padding: 2px 0;
    & + .fact { border-left: 1px solid $line-soft; }
}
.fact-name { font-size: 11px; color: $sub-2; white-space: nowrap; }
.fact-value { font-size: 13px; font-weight: 600; white-space: nowrap; }

/* ── 업종 내 종목 ── */
.st-list { list-style: none; margin: 0; padding: 0; }
.st-list li + li { border-top: 1px solid $line-soft; }
.st-row {
    width: 100%;
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    column-gap: 10px;
    align-items: center;
    border: 0;
    background: transparent;
    padding: 10px 0;
    text-align: left;
    cursor: pointer;
    color: $ink;
    font-family: inherit;

    .who { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
    .name-line { display: flex; align-items: baseline; gap: 5px; min-width: 0; }   // 순위는 종목명 줄 안에
    .rank { font-family: 'Do Hyeon', 'Pretendard', sans-serif; font-size: 15px; line-height: 1; color: $amber; flex-shrink: 0; }
    .name { font-size: 14px; font-weight: 600; overflow-wrap: anywhere; }
    .code { font-size: 11px; color: $sub-2; }
    .px { display: flex; flex-direction: column; align-items: flex-end; gap: 2px; }
    .price { font-size: 14px; font-weight: 700; }
    .chg-sm { font-size: 12px; font-weight: 600; color: $sub; &.up { color: $up; } &.down { color: $down; } }
}

.more {
    width: 100%;
    margin-top: 4px;
    padding: 10px 0;
    border: 0;
    border-top: 1px solid $line-soft;
    background: transparent;
    font: inherit;
    font-size: 13px;
    font-weight: 600;
    color: $brown;
    cursor: pointer;
}

.state {
    padding: 40px 0;
    text-align: center;
    font-size: 13px;
    color: $sub-2;
}
</style>
