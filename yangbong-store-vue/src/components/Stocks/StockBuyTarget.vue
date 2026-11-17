<template>
    <div id="stock-buy-target">
        <!-- 주식분석 탭의 첫 화면이라 뒤로 버튼이 없다(/stock 은 여기로 다시 온다). -->
        <BrandHeader :title="title" />

        <div class="contents">
            <!-- ── 1줄: 추천 단계 칩(선택 = 꿀색) + 오른쪽 날짜 ‹ 11.17 (화) ›
                 단계는 열람 가능한 단계 + 바로 위 한 단계(잠금)만 보인다. 그 위 단계는 존재 자체를 숨긴다 ── -->
            <div class="top-bar">
                <div class="stage-chips" role="tablist" aria-label="추천 단계">
                    <button v-for="s in visibleStages" :key="s.code" type="button" role="tab" class="stage-chip"
                        :class="{ on: s.code === stageCode, locked: s.locked }"
                        :aria-selected="s.code === stageCode ? 'true' : 'false'" @click="stageCode = s.code">
                        <svg v-if="s.locked" class="stage-lock" width="13" height="13" viewBox="0 0 16 16" fill="none"
                            stroke="currentColor" stroke-width="1.6" stroke-linecap="round" aria-hidden="true">
                            <rect x="3" y="7" width="10" height="7" rx="2" /><path d="M5.5 7V5a2.5 2.5 0 0 1 5 0v2" />
                        </svg>
                        {{ s.name }}
                        <span class="stage-count">{{ s.locked ? '' : (s.ready === false ? '준비 중' : stageCount(s.rank)) }}</span>
                    </button>
                </div>
                <!-- 날짜: 가운데를 눌러 달력으로 고르고, 양옆으로 하루씩(주말 건너뜀) 옮긴다 -->
                <div class="date-nav">
                    <button type="button" class="nav-btn" aria-label="이전 영업일" @click="stepSelectedDate(-1)">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m15 18-6-6 6-6"></path></svg>
                    </button>
                    <div class="date-center">
                        <button type="button" class="date-btn" aria-label="날짜 선택" @click="openDatePicker">{{ dateLabel }}</button>
                        <input type="date" ref="dateInput" class="hidden-input" v-model="selectedDate"
                            @change="handleDateChange" tabindex="-1" aria-hidden="true" />
                    </div>
                    <button type="button" class="nav-btn" aria-label="다음 영업일" :disabled="!canStepForward" @click="stepSelectedDate(1)">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m9 6 6 6-6 6"></path></svg>
                    </button>
                </div>
            </div>
            <div class="band" aria-hidden="true"></div>

            <!-- 잠금 단계를 고른 경우: 내용 대신 안내만(개수·종목은 서버가 내려주지 않는다) -->
            <section v-if="activeStage.locked" class="stage-locked">
                <svg width="22" height="22" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"
                    stroke-linecap="round" aria-hidden="true"><rect x="3" y="7" width="10" height="7" rx="2" /><path d="M5.5 7V5a2.5 2.5 0 0 1 5 0v2" /></svg>
                <p class="stage-locked-title">{{ activeStage.name }} 추천이 따로 있어요</p>
                <p class="stage-locked-desc">{{ activeStage.desc }}</p>
                <p v-if="activeStage.unlock" class="stage-locked-unlock">{{ activeStage.unlock }}</p>
            </section>

            <!-- 아직 알고리즘이 확정되지 않은 단계(실전): 빈 목록 대신 준비 중 안내 -->
            <section v-else-if="activeStage.ready === false" class="stage-locked">
                <p class="stage-locked-title">{{ activeStage.name }} 추천을 준비하고 있어요</p>
                <p class="stage-locked-desc">{{ activeStage.desc }}</p>
            </section>

            <template v-else>
            <!-- ── 2줄: 목록 머리 + 정렬·범위 선택(누르면 기기 기본 선택 창이 뜬다) ── -->
            <div class="list-head">
                <h2>추천 종목<span v-if="!isLoading" class="count">{{ sortedData.length }}</span></h2>
                <span class="basis">{{ priceLabel }} 기준</span>
            </div>
            <div class="filters">
                <label class="fbtn">
                    <span class="sr-only">정렬 기준</span>
                    <b>{{ currentSort.label }}</b>
                    <select v-model="sortKey" @change="onSortKeyChange">
                        <option v-for="o in SORT_OPTIONS" :key="o.key" :value="o.key">{{ o.label }}</option>
                    </select>
                </label>
                <label class="fbtn">
                    <span class="sr-only">목록 범위</span>
                    {{ personaType.name }} · <b>{{ mineOnly ? '내 조건만' : '전체' }}</b>
                    <select :value="mineOnly ? 'mine' : 'all'" @change="onScopeChange">
                        <option value="mine">{{ personaType.name }} · 내 조건만</option>
                        <option value="all">{{ personaType.name }} · 전체</option>
                        <option value="preset">내 설정 바꾸기…</option>
                    </select>
                </label>
            </div>

            <section class="buy-target reco">
                <div v-if="!isLoading && sortedData.length" class="reco-list">
                    <div v-for="(r, idx) in rows" :key="r.item.stock_code ?? idx" class="reco-item">
                        <!-- 윗줄: 순위 | 종목명·코드·시총 | 가격·등락 배지. 아래: 추천 이유 한 줄(크림 띠) + 내 조건 점. 전체가 펼침 버튼 -->
                        <button type="button" class="reco-row" :class="{ open: expandedCode === r.item.stock_code }"
                            :aria-expanded="expandedCode === r.item.stock_code ? 'true' : 'false'"
                            @click="toggleRow(r.item.stock_code)">
                            <span class="rank">{{ rankNumber(idx) }}</span>
                            <span class="name">{{ r.item.stock_name }}</span>
                            <span class="price">{{ formatNumber(r.item.close) }}</span>
                            <span class="badge" :class="r.chg.cls">{{ r.chgPct }}</span>

                            <!-- 추천 이유 한 줄 + 나머지 개수 + 내 조건 점(펼치면 '내 조건 N개 중 M개 충족'으로 풀어 쓴다) -->
                            <span v-if="expandedCode !== r.item.stock_code && (r.reasons.top || r.passTotal)" class="why">
                                <template v-if="r.reasons.top">
                                    <span class="why-ic" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="m5 12.5 4.5 4.5L19 7.5"></path></svg></span>
                                    <span class="why-tx">{{ r.reasons.top.text }}<em v-if="r.reasons.rest">+{{ r.reasons.rest }}</em></span>
                                </template>
                                <span v-else class="why-tx muted">충족한 지표가 없어요</span>
                                <span v-if="r.passTotal" class="dots" :title="`내 조건 ${r.passTotal}개 중 ${r.passCount}개 충족`"
                                    :aria-label="`내 조건 ${r.passTotal}개 중 ${r.passCount}개 충족`">
                                    <i v-for="n in r.passTotal" :key="n" :class="{ f: n <= r.passCount }"></i>
                                </span>
                            </span>
                        </button>

                        <!-- 펼침: 이유(말) → 아직 아닌 것 → 숫자 → 버튼 -->
                        <div v-if="expandedCode === r.item.stock_code" class="reco-detail">
                            <p class="rd-meta">
                                {{ r.item.stock_code }}<template v-if="r.capShort"> · 시총 {{ r.capShort }}</template><template v-if="r.item.sector_name"> · {{ r.item.sector_name }}</template>
                                <span v-if="r.passTotal" class="rd-match">내 조건 {{ r.passTotal }}개 중 <b>{{ r.passCount }}개</b> 충족</span>
                            </p>
                            <template v-if="r.reasons.passed.length">
                                <h4 class="rd-h">추천 이유 {{ r.reasons.passed.length }}가지</h4>
                                <ul class="rs">
                                    <li v-for="x in r.reasons.passed" :key="x.key">
                                        <span class="rs-k" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="m5 12.5 4.5 4.5L19 7.5"></path></svg></span>
                                        <span>{{ x.text }}<small>{{ x.detail }}</small></span>
                                    </li>
                                </ul>
                            </template>
                            <template v-if="r.reasons.failed.length">
                                <h4 class="rd-h">아직 아닌 것</h4>
                                <ul class="rs off">
                                    <li v-for="x in r.reasons.failed" :key="x.key">
                                        <span class="rs-k" aria-hidden="true"></span>
                                        <span>{{ x.text }} · {{ x.detail }}</span>
                                    </li>
                                </ul>
                            </template>

                            <!-- 숫자: PER·PBR·점수(프리미엄은 외국인·기관 순매수까지). 수급은 추천일 이하 최근 영업일, PER/PBR 은 추천일 배치 시점 -->
                            <div class="facts">
                                <span v-for="f in r.facts" :key="f.name" class="fact">
                                    <span class="fact-name">{{ f.name }}</span>
                                    <span class="fact-value" :class="f.cls">{{ f.value }}</span>
                                </span>
                                <span v-if="hasValue(r.item.score)" class="fact">
                                    <span class="fact-name">종합 점수</span>
                                    <span class="fact-value">{{ numOrNull(r.item.score) }}</span>
                                </span>
                            </div>
                            <!-- 시가총액 · 수급(프리미엄 단계): 추천일 이하 가장 최근 영업일 기준. 순매수=빨강 / 순매도=파랑 -->
                            <div v-if="r.market && activeStage.rank >= 2" class="mk">
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

                            <div class="rd-actions">
                                <button type="button" class="btn strong" @click="goToStockInfo(r.item.stock_code, r.item.stock_name)">AI 분석 보기</button>
                                <button type="button" class="btn" @click="toggleChart(r.item.stock_code)">
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
            </template>
        </div>
    </div>
</template>

<script setup>
import CandlestickChart from '../common/comp/CandlestickChart.vue';
import { buyTargetCandleData, miniCandleOptions } from '@scripts/miniCandle.js';
import aibeesApi from '@scripts/aibeesApi.js';
import { recoLevel } from '@scripts/useAccess.js';
import { addRecent } from '@scripts/recentStocks.js';
import { usePersonaStore } from '@scripts/stores/persona-store.js';
import { orderForType } from '@scripts/persona.js';
import { evaluate } from '@scripts/indicators.js';
import { recoReasons } from '@scripts/recoReasons.js';
import { ONBOARDING_PATH } from '@scripts/authPaths.js';
import {
    numOrNull, formatNumber, hasValue, changeInfo, conditionSummary,
    kstNowParts, isMarketOpenNow, weekdayKo, toYmdString, shiftDate, getLatestBatchDate,
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
    return `${m}.${d} (${weekdayKo(selectedDate.value)})`;
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
const openDatePicker = () => dateInput.value?.showPicker?.();

/* ── 날짜 ±1 이동 (예전 홈과 같은 규칙: 주말은 건너뛴다 — 금요일 +1 → 월요일, 월요일 −1 → 금요일) ──
 *   가장 최근 배치일보다 뒤로는 데이터가 없어 › 를 막는다(달력으로 고르는 건 그대로 둔다). */
const latestBatchDate = getLatestBatchDate();
const canStepForward = computed(() => selectedDate.value < latestBatchDate);
const stepSelectedDate = (deltaDays) => {
    if (deltaDays > 0 && !canStepForward.value) return;
    const [y, m, d] = selectedDate.value.split('-').map(Number);
    let next = shiftDate(y, m, d, deltaDays);
    while (next.weekday === 0 || next.weekday === 6) {
        next = shiftDate(next.year, next.month, next.day, deltaDays > 0 ? 1 : -1);
    }
    selectedDate.value = toYmdString(next.year, next.month, next.day);
    getStockMainData();
};

/* ══════════════ 매수타겟 정렬 ══════════════
 * 조회는 하루치 전체를 한 번에 받아오므로 클라이언트에서 정렬한다(재조회 없음).
 *
 * 규칙은 worker(trade_worker/repository.py _ORDER_FIELDS)와 맞춘다:
 *   · 필드별 기본 방향 — rank_no 는 작을수록 상위(asc), score/volume 은 클수록 상위(desc)
 *   · 값이 없는(null) 종목은 정렬 방향과 무관하게 항상 뒤
 *   · 전부 동점이면 stock_code 로 최종 결정 (매 조회마다 순서가 흔들리지 않도록)
 */
// 열람 가능한 최고 단계. 실전 = WORKER_USER 권한(운영자 부여), 프리미엄 = RECO_ADVANCED 기능 플래그(광고·구독으로 부여 예정).
// 서버(/buy-target)가 같은 기준으로 권한 밖 정보를 응답에서 지운다 — 여기는 화면 구성용일 뿐 보안이 아니다.
const route = useRoute();
const userLevel = computed(() => {
    if (import.meta.env.DEV) {   // 개발 중 미리보기 전용(?level=1|2|3)
        const q = Number(route.query.level);
        if (q >= 1 && q <= 3) return q;
    }
    return recoLevel();
});

// 프리미엄 단계 이상에서만 값이 내려오는 정렬 기준(기본 단계에는 서버가 이 필드를 주지 않는다)
const ADVANCED_SORT_KEYS = ['composite_rank_no', 'shape_proba', 'frgn_amt', 'orgn_amt'];
const SORT_ALL = [
    { key: 'persona',    label: '내 성향 순서',  dir: 'asc',  ascLabel: '성향에 맞는 순',  descLabel: '거꾸로' },
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
//   기본 단계: 옛 알고리즘이 채우는 추천순위·점수 / 프리미엄 단계: 2파 알고리즘의 종합순위·모델 확률·수급
const BASIC_ONLY_SORT_KEYS = ['rank_no', 'score'];
const persona = usePersonaStore();
const personaType = computed(() => persona.currentType);
// 내 설정의 보조지표로 다시 거른 목록만 볼지(기본) 서버 후보 전체를 볼지
const mineOnly = ref(true);
const SORT_OPTIONS = computed(() => (activeStage.value.rank >= 2
    ? SORT_ALL.filter(o => !BASIC_ONLY_SORT_KEYS.includes(o.key))
    : SORT_ALL.filter(o => !ADVANCED_SORT_KEYS.includes(o.key))));

// 2026-09 세션 후속: 2단계(top10→모멘텀 재정렬) 방식이 우수해 프리미엄 단계 기본 정렬은 composite_rank_no. 기본 단계는 추천순위.
const sortKey = ref('persona');   // 기본 정렬 = 내 성향 순서(안정형 시가총액 큰 순 / 균형형 서버 순서 / 공격형 변동 큰 순)
const sortDir = ref('asc');

const currentSort = computed(
    () => SORT_OPTIONS.value.find(o => o.key === sortKey.value) ?? SORT_OPTIONS.value[0]);

// select 의 v-model 이 sortKey 를 이미 바꿔 놓은 뒤에 불린다. 기준을 바꾸면 그 필드의 기본 방향으로 되돌린다.
// (거래량을 고르고 '적은 순'이 남아 있으면 의도와 반대 결과가 나온다)
const onSortKeyChange = () => {
    sortDir.value = SORT_OPTIONS.value.find(o => o.key === sortKey.value)?.dir ?? 'desc';
};
const toggleSortDir = () => { sortDir.value = sortDir.value === 'desc' ? 'asc' : 'desc'; };
// 범위 선택: 내 조건만 / 전체 / 내 설정 바꾸기(설정 화면으로 이동 — 선택값은 그대로 둔다)
const onScopeChange = (e) => {
    const v = e.target.value;
    if (v === 'preset') { e.target.value = mineOnly.value ? 'mine' : 'all'; router.push('/stock/preset'); return; }
    mineOnly.value = v === 'mine';
};

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

/* ══════════════ 추천 단계(기본 → 프리미엄 → 실전) ══════════════
 * 단계 이름·설명은 임시 — 확정되면 STAGE_DEFS 만 바꾼다. desc 는 잠겼을 때도 보이므로 내부 용어를 쓰지 않는다.
 * 단계마다 알고리즘이 다른 별개의 목록이다. 서버(RecoLevel.py)가 행마다 reco_stages(속한 단계 번호, 사용자 단계까지)를 준다.
 *   기본 = 옛 기계식 / 프리미엄 = 2파 돌파 + 모델 확률 + 외국인·기관 수급 / 실전 = 프리미엄 종목의 30분봉 재검증(연구 중).
 * 서버는 사용자 권한 밖 종목·정보를 응답에서 지운다(화면 가림은 보안이 아니다).
 */
const STAGE_DEFS = [
    // 기본 = 옛 기계식 알고리즘(이평 정배열·MACD/OBV 기울기·거래량 급증 등)
    { code: 'BASIC', rank: 1, name: '기본', desc: '이동평균·거래량 같은 규칙으로 1차로 고른 후보예요.' },
    // 프리미엄 = 현재 제공 알고리즘(2파 하락 추세선 돌파 + 모델 확률 + 외국인·기관 수급). 잠겼을 때도 보이는 문구라 내부 용어는 쓰지 않는다.
    //   광고 시청·정기결제 연동 전이라 버튼은 아직 없다.
    { code: 'ADVANCED', rank: 2, name: '프리미엄', desc: '차트 패턴과 모델 분석, 수급 흐름까지 더해 고른 종목이에요.',
      unlock: '광고를 보거나 정기결제를 하면 열려요.' },
    // 실전 = 프리미엄 종목을 30분봉으로 다시 검증해 순위를 재정비한 목록(다른 세션에서 연구 중 — ready:false).
    //   private: 운영자가 직접 권한(WORKER_USER)을 준 사람만. 신청·결제 경로가 없으므로 권한이 없으면 칩 자체를 숨긴다.
    { code: 'LIVE', rank: 3, name: '실전', desc: '프리미엄 종목을 30분봉으로 한 번 더 검증한 최종 후보를 곧 보여드릴게요.', private: true, ready: false },
];
const visibleStages = computed(() =>
    STAGE_DEFS
        .filter(d => d.rank <= userLevel.value + 1)
        .map(d => ({ ...d, locked: d.rank > userLevel.value }))
        .filter(d => !(d.locked && d.private)));
const stageCode = ref('BASIC');
const activeStage = computed(() => visibleStages.value.find(s => s.code === stageCode.value) ?? visibleStages.value[0]);
// 단계를 바꾸면 그 단계의 기본 정렬로 되돌린다(단계마다 쓸 수 있는 정렬 기준이 다르다)
watch(stageCode, () => {
    sortKey.value = 'persona';
    sortDir.value = 'asc';
});
// 단계 k 의 목록 = 서버가 reco_stages 에 k 를 담아 준 종목. 단계마다 알고리즘이 달라 서로 다른 목록이며
// 두 알고리즘에 모두 걸린 종목은 양쪽에 나온다. reco_stages 가 없으면(구 응답) 기본 단계로 본다.
const stageItems = (rank) => resultData.value.filter(it => (it.reco_stages ?? [1]).includes(rank));
const stageCount = (rank) => stageItems(rank).length;

const sortedData = computed(() => {
    const key = sortKey.value;
    const desc = sortDir.value === 'desc';
    let base = activeStage.value.locked ? [] : stageItems(activeStage.value.rank);
    if (mineOnly.value) base = base.filter(it => evaluate(it, personaType.value.settings).match);
    if (key === 'persona') {
        // 같은 성향이면 누가 보든 같은 순서(동률은 서버 순서). 방향 버튼은 이 순서를 뒤집는다.
        const ordered = orderForType(base, personaType.value);
        return desc ? ordered.reverse() : ordered;
    }
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
        const ev = evaluate(item, personaType.value.settings);
        const summary = conditionSummary(item);
        return {
            item, chg, chgShort: shortChange(chg),
            chgPct: chg.pct === null ? '' : `${chg.dir > 0 ? '+' : (chg.dir < 0 ? '−' : '')}${Math.abs(chg.pct).toFixed(2)}%`,
            passText: ev.total ? `${ev.pass}/${ev.total}` : '–',
            passCount: ev.pass ?? 0,
            passTotal: ev.total ?? 0,
            summary,
            // 목록 줄에는 충족한 지표만 태그로, 펼치면 충족 먼저 → 미달 순서로 7개 전부
            passedConds: summary.rows.filter(c => c.pass).map(c => COND_NAMES[c.key] ?? c.head),
            condsSorted: [...summary.rows].sort((x, y) => Number(y.pass) - Number(x.pass)),
            reasons: recoReasons(item),   // 추천 이유 문장(목록 줄 1개 + 펼침 전체)
            capShort: formatCapShort(item.market_cap), market: marketInfo(item),
            recentBars: (item.chart_data || []).slice(-RECENT_BARS),
            facts: [
                // 수급은 프리미엄 정보 — 기본 단계는 서버가 값을 주지 않으므로 칸도 그리지 않는다
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
const toggleRow = (code) => {
    expandedCode.value = expandedCode.value === code ? null : code;
    // 상세를 연 회사는 주식분석 대시보드의 "최근 본 회사"에 남는다
    if (expandedCode.value) addRecent(code, resultData.value.find(it => it.stock_code === code)?.stock_name);
};
watch([sortKey, sortDir, selectedDate, mineOnly], () => { expandedCode.value = null; });

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
// 2026-11-17 꿀빛 톤(한국투자 참고) — 홈과 같은 토큰. 조작 줄 2줄, 종목마다 추천 이유 한 줄(크림 띠).
@use '@@/_home-tokens.scss' as *;

#stock-buy-target {
    min-height: 100vh;
    background: $card;
    color: $ink;
    text-align: left;
    font-family: $font-body;
    font-variant-numeric: tabular-nums;
    letter-spacing: -0.2px;
    -webkit-font-smoothing: antialiased;
}
button { font: inherit; letter-spacing: inherit; }
.sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }

.contents { max-width: 720px; margin: 0 auto; padding: 0 0 24px; }

/* ── 1줄: 단계 칩 + 날짜 ── */
.top-bar { display: flex; align-items: center; gap: 8px; padding: 6px 12px 0 $pad-x; }
.stage-chips { display: flex; gap: 6px; min-width: 0; }
.stage-chip {
    height: 36px;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 0 14px;
    border: 0;
    border-radius: 8px;
    background: transparent;
    color: $sub;
    font-size: 15px;
    font-weight: 500;
    white-space: nowrap;
    cursor: pointer;
    -webkit-tap-highlight-color: transparent;
    .stage-count { font-size: 14px; font-weight: 600; font-variant-numeric: tabular-nums; }
    &.on { background: $honey-300; color: $honey-ink; font-weight: 700; .stage-count { color: $amber-700; } }
    &:focus-visible { outline: 2px solid $ink; outline-offset: 2px; }
}
.date-nav { margin-left: auto; display: flex; align-items: center; flex: none; }
.nav-btn {
    width: 28px;
    height: 40px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border: 0;
    background: transparent;
    color: $sub;
    cursor: pointer;
    &:disabled { color: $line; cursor: default; }
}
.date-center { position: relative; }
.date-btn {
    height: 40px;
    padding: 0 2px;
    border: 0;
    background: transparent;
    color: $ink;
    font-size: 14px;
    font-weight: 600;
    white-space: nowrap;
    cursor: pointer;
}
.hidden-input { position: absolute; left: 50%; bottom: 0; width: 0; height: 0; opacity: 0; pointer-events: none; }
.band { height: $band-h; margin-top: 16px; background: $band; }

.stage-locked {
    display: flex; flex-direction: column; align-items: center; gap: 6px;
    margin: 20px $pad-x 0; padding: 32px 20px; border-radius: $radius; background: $honey-50; text-align: center; color: $ink;
    svg { color: $amber-700; }
    .stage-locked-title { margin: 4px 0 0; font-size: 16px; font-weight: 700; }
    .stage-locked-desc { margin: 0; font-size: 14px; line-height: 1.5; color: $sub-ink; text-wrap: pretty; }
    .stage-locked-unlock { margin: 6px 0 0; padding: 6px 12px; border-radius: 8px; background: $card; font-size: 13px; font-weight: 600; color: $amber-700; }
}

/* ── 2줄: 목록 머리 + 정렬·범위 ── */
.list-head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    padding: 24px $pad-x 0;
    h2 { margin: 0; font-size: 20px; font-weight: 700; letter-spacing: -0.5px; }
    .count { margin-left: 4px; color: $amber-700; }
    .basis { font-size: 13px; color: $sub; }
}
.filters { display: flex; gap: 6px; padding: 12px $pad-x 4px; }
.fbtn {
    position: relative;
    height: 34px;
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 0 10px 0 12px;
    border: 1px solid $line;
    border-radius: 8px;
    font-size: 14px;
    color: $sub-ink;
    white-space: nowrap;
    cursor: pointer;
    b { color: $ink; font-weight: 600; }
    &::after {
        content: '';
        width: 6px;
        height: 6px;
        margin: 0 0 3px 6px;
        border-right: 1.6px solid $sub;
        border-bottom: 1.6px solid $sub;
        transform: rotate(45deg);
    }
    // 실제 선택은 위에 투명하게 덮은 select(기기 기본 선택 창)
    select { position: absolute; inset: 0; width: 100%; height: 100%; opacity: 0; cursor: pointer; font-size: 16px; }
    &:focus-within { box-shadow: 0 0 0 2px $ink; }
}

/* ── 종목 목록 ── */
.reco { padding: 0 $pad-x; }
.reco-list { display: flex; flex-direction: column; }
.reco-item + .reco-item { border-top: 1px solid $line; }

.reco-row {
    width: 100%;
    display: grid;
    grid-template-columns: 26px minmax(0, 1fr) auto;
    align-items: start;
    padding: 18px 0 14px;
    border: 0;
    background: transparent;
    text-align: left;
    cursor: pointer;
    color: $ink;
    -webkit-tap-highlight-color: transparent;

    .rank { font-size: 17px; font-weight: 700; line-height: 1.4; color: $amber-700; }
    .who { display: flex; flex-direction: column; gap: 2px; min-width: 0; padding-right: 12px; }
    .name-line { display: flex; align-items: baseline; gap: 6px; min-width: 0; }
    .name {
        font-size: 17px;
        font-weight: 600;
        line-height: 1.4;
        letter-spacing: -0.4px;
        min-width: 0;
        overflow-wrap: anywhere;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
    }
    .sector { font-size: 12px; color: $sub; white-space: nowrap; flex-shrink: 0; }
    .code { font-size: 13px; color: $sub; }
    .px { display: flex; flex-direction: column; align-items: flex-end; gap: 4px; }
    .price { font-size: 17px; font-weight: 600; line-height: 1.4; }

    // 추천 이유 한 줄
    .why {
        grid-column: 2 / -1;
        display: flex;
        align-items: center;
        gap: 8px;
        margin-top: 12px;
        padding: 11px 12px;
        border-radius: 10px;
        background: $honey-50;
    }
    .why-tx { flex: 1; min-width: 0; font-size: 14px; color: $honey-ink; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .why-more { flex: none; font-size: 13px; font-weight: 600; color: $amber-700; }

    .r2 {
        grid-column: 2 / -1;
        display: flex;
        align-items: center;
        margin-top: 10px;
        font-size: 12px;
        color: $sub;
    }
    .match { display: inline-flex; align-items: center; gap: 5px; white-space: nowrap; b { color: $ink; font-weight: 600; } }
    .dots { display: inline-flex; gap: 3px; }
    .dots i { width: 6px; height: 6px; border-radius: 3px; background: $line; }
    .dots i.f { background: $amber-700; }
    .more-hint { margin-left: auto; display: inline-flex; align-items: center; gap: 2px; font-size: 12px; color: $sub; }
    .more-chev { color: $sub-2; transition: transform .15s ease; }
    &.open .more-chev { transform: rotate(180deg); }
}
.why-ic, .rs-k {
    width: 18px;
    height: 18px;
    border-radius: 9px;
    background: $honey-300;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    svg { width: 10px; height: 10px; fill: none; stroke: $honey-ink; stroke-width: 2.6; stroke-linecap: round; stroke-linejoin: round; }
}

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

/* ── 펼친 상세: 이유 → 아직 아닌 것 → 숫자 → 버튼 ── */
.reco-detail { margin-left: 26px; padding: 0 0 20px; display: flex; flex-direction: column; }
.rd-h { margin: 4px 0 6px; font-size: 13px; font-weight: 600; color: $sub; }
.rs + .rd-h { margin-top: 12px; }
.rs { list-style: none; margin: 0; padding: 0; }
.rs li {
    display: flex;
    gap: 10px;
    align-items: flex-start;
    padding: 7px 0;
    font-size: 15px;
    line-height: 1.45;
    .rs-k { flex: none; margin-top: 2px; }
    small { display: block; margin-top: 1px; font-size: 12px; color: $sub; }
}
.rs.off li { padding: 5px 0; font-size: 14px; color: $sub; .rs-k { background: $band; } }

.facts {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 10px 8px;
    margin-top: 14px;
    padding: 14px;
    border-radius: $radius;
    background: $band;
}
.fact { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
.fact-name { font-size: 12px; color: $sub; white-space: nowrap; }
.fact-value {
    font-size: 15px;
    font-weight: 600;
    color: $ink;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    &.up   { color: $up; }
    &.down { color: $down; }
}

.mk { margin-top: 14px; }
.mk-head { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; }
.mk-title { font-size: 13px; font-weight: 600; color: $ink; }
.mk-date  { font-size: 12px; color: $sub-2; }
.mk-list { margin: 0; padding: 0; list-style: none; }
.mk-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    min-height: 34px;
    font-size: 14px;
    .mk-label { color: $sub; white-space: nowrap; }
    .mk-value { font-weight: 600; color: $ink; text-align: right; white-space: nowrap; &.up { color: $up; } &.down { color: $down; } }
    .mk-qty { margin-left: 6px; font-size: 12px; font-weight: 400; color: $sub-2; }
}

.rd-actions { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; margin-top: 12px; }
.btn {
    min-height: 46px;
    border: 0;
    border-radius: $radius;
    background: $band;
    color: $ink;
    font-size: 15px;
    font-weight: 600;
    cursor: pointer;
    &.strong { background: $honey-300; color: $honey-ink; }
}

.skeleton-row { height: 120px; border-top: 1px solid $line; background: $honey-50; animation: pulse 1.6s infinite ease-in-out; }
.empty-box { text-align: center; padding: 56px 0; color: $sub; font-size: 14px; }

/* ── 간이 차트 ── */
.mini-chart {
    width: 100%;
    margin-top: 14px;
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
    .mini-chart-detail { flex-shrink: 0; min-height: 32px; padding: 0 4px; border: 0; background: transparent; color: $sub-ink; font-size: 13px; cursor: pointer; }
    .mini-chart-canvas { width: 100%; height: 220px; }
}

@keyframes pulse {
    0%, 100% { opacity: .5; }
    50%       { opacity: .9; }
}

/* ── 2026-11-17 v3 '숨 쉬는 버전': 종목 하나 = 2층(한 줄 + 이유 띠). 코드·시총·내 조건 글자는 펼쳤을 때만 ── */
.band { margin-top: 0; }
.top-bar { padding-bottom: 16px; }
.list-head { padding-top: 32px; }
.filters { padding-top: 14px; padding-bottom: 8px; }
.reco-row {
    grid-template-columns: 28px minmax(0, 1fr) auto auto;
    column-gap: 0;
    align-items: center;
    padding: 20px 0;
    .name {
        display: block;
        min-width: 0;
        padding-right: 12px;
        font-size: 16px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        -webkit-line-clamp: unset;
    }
    .price { font-size: 16px; font-weight: 600; margin-right: 12px; }
    .badge { min-width: 62px; justify-content: center; height: 24px; }
    .why { margin-top: 12px; }
    .why-tx em { font-style: normal; margin-left: 4px; font-weight: 600; color: $amber-700; }
    .why-tx.muted { color: $sub; }
}
.why .dots { display: inline-flex; gap: 3px; flex: none; }
.why .dots i { width: 6px; height: 6px; border-radius: 3px; background: #E8E2D0; }
.why .dots i.f { background: $amber-700; }
.reco-detail { margin-left: 28px; }
.rd-meta {
    margin: 0 0 12px;
    font-size: 13px;
    color: $sub;
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    gap: 4px 12px;
    .rd-match { color: $sub-ink; b { color: $amber-700; font-weight: 600; } }
}
</style>
