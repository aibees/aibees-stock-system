<template>
    <div id="home">
        <Headers :prop_title="title" />

        <div class="contents">
            <!-- ════════ 추천종목 섹션 (제목+정렬+카드를 한 패널로 묶음 — 아래에 다른 섹션이 이어 붙을 예정) ════════ -->
            <section class="reco-section">
                <div class="head-desc">
                <div class="head-left">
                    <h2 style="text-align: left;">오늘의 추천종목</h2>
                </div>

                <div class="head-actions">
                    <div class="date-nav">
                        <button type="button" class="date-arrow" title="이전 영업일" @click="stepSelectedDate(-1)">‹</button>
                        <div class="date-picker-trigger" @click="openDatePicker">
                            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none"
                                stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect>
                                <line x1="16" y1="2" x2="16" y2="6"></line>
                                <line x1="8" y1="2" x2="8" y2="6"></line>
                                <line x1="3" y1="10" x2="21" y2="10"></line>
                            </svg>
                            <span class="date-value">{{ formattedDisplayDate }}</span>
                            <input type="date" ref="dateInput" class="hidden-input" v-model="selectedDate"
                                @change="handleDateChange" />
                        </div>
                        <button type="button" class="date-arrow" title="다음 영업일" @click="stepSelectedDate(1)">›</button>
                    </div>
                    <button type="button" class="btn-detail" @click="goToBuyTargetDetail">상세보기 ›</button>
                </div>
                </div>

                <!-- ── 정렬 옵션 ── -->
                <div v-if="!isLoading && resultData.length > 0" class="sort-bar">
                <span class="sort-label">정렬</span>
                <div class="sort-chips">
                    <button v-for="o in SORT_OPTIONS" :key="o.key" type="button"
                        :class="['sort-chip', { on: sortKey === o.key }]"
                        @click="setSortKey(o.key)">
                        {{ o.label }}
                    </button>
                </div>
                <button type="button" class="sort-dir" @click="toggleSortDir"
                    :title="sortDir === 'desc' ? '내림차순' : '오름차순'">
                    <span class="dir-arrow">{{ sortDir === 'desc' ? '↓' : '↑' }}</span>
                    {{ sortDir === 'desc' ? currentSort.descLabel : currentSort.ascLabel }}
                </button>
                </div>

                <!-- ── 최우선타겟 선택: 추천 항목 중 사용자가 직접 하나를 지정 ── -->
                <div v-if="!isLoading && resultData.length > 0" class="priority-bar">
                <span class="priority-label">최우선타겟</span>
                <select class="priority-select" v-model="priorityTarget" @change="onPriorityChange">
                    <option :value="null">선택 안 함</option>
                    <!-- 저장된 최우선타겟이 지금 보고 있는 날짜 목록에 없으면(다른 날짜에서
                         지정한 값) 그래도 선택 상태가 보이도록 임시 옵션을 하나 얹는다. -->
                    <option v-if="priorityTarget && !sortedData.some(i => i.stock_code === priorityTarget)"
                        :value="priorityTarget">
                        {{ priorityTargetName || priorityTarget }} (다른 날짜)
                    </option>
                    <option v-for="item in sortedData" :key="item.stock_code" :value="item.stock_code">
                        {{ item.stock_name }} ({{ item.stock_code }})
                    </option>
                </select>
                </div>

                <div class="buy-target">
                <div v-if="!isLoading && pagedData.length > 0" class="signal-grid">
                    <div v-for="(item, index) in pagedData" :key="item.stock_code ?? index" class="signal-card"
                        :class="{ 'is-priority': item.stock_code === priorityTarget }">

                        <!-- 헤더: 순위 + 종목명/코드 + 액션 버튼 + 금일 변동률 -->
                        <div class="card-head">
                            <div class="rank-num">{{ String(currentPage * PAGE_SIZE + index + 1).padStart(2, '0') }}</div>
                            <div class="head-main">
                                <h3 class="name">{{ item.stock_name }}</h3>
                                <div class="code">{{ item.stock_code }}</div>
                                <span v-if="item.stock_code === priorityTarget" class="priority-badge">최우선타겟</span>
                            </div>
                            <div class="actions-row">
                                <button class="action-btn ai-btn" @click="goToStockInfo(item.stock_code, item.stock_name)">AI 분석</button>
                                <button class="action-btn chart-btn" @click="toggleChart(item.stock_code)">
                                    {{ expandedCharts.has(item.stock_code) ? '차트접기' : '차트보기' }}
                                </button>
                            </div>
                            <div class="rate-badge" :class="rateClass(item.rate)">{{ item.rate ?? '-' }}</div>
                        </div>

                        <!-- 간이 차트: 최근 120영업일 봉차트 + 20/60/120일선 (기본 숨김, 차트보기로 토글) -->
                        <div v-if="expandedCharts.has(item.stock_code) && item.chart_data && item.chart_data.length" class="mini-chart">
                            <div class="mini-chart-head">
                                <div class="mini-legend">
                                    <span class="leg-item" style="--c:#efa55b">MA20</span>
                                    <span class="leg-item" style="--c:#d0fe48">MA60</span>
                                    <span class="leg-item" style="--c:#01b6f3">MA120</span>
                                </div>
                                <button type="button" class="mini-chart-detail" @click="goToChart(item.stock_code)">자세히보기 ›</button>
                            </div>
                            <div class="mini-chart-canvas">
                                <CandlestickChart :chartData="buyTargetCandleData(item)" :extraOptions="miniCandleOptions" />
                            </div>
                        </div>

                        <!-- 현재가 + 거래량 + 추천 -->
                        <div class="stat-pair triple">
                            <div class="stat-cell">
                                <span class="stat-label">현재가</span>
                                <div class="stat-main">{{ formatNumber(item.close) }}<span class="unit">원</span></div>
                            </div>
                            <div class="stat-cell">
                                <span class="stat-label">거래량</span>
                                <div class="stat-main">{{ formatVolume(item.volume || 0) }}</div>
                            </div>
                            <div class="stat-cell">
                                <span class="stat-label">점수</span>
                                <div class="stat-main" :class="scoreClass(item.score)">{{ item.score ?? '-' }}<span class="unit">/100</span></div>
                            </div>
                        </div>

                        <!-- 시/고/저/종 -->
                        <div class="price-row">
                            <div class="price-item">
                                <span class="price-label">시가</span>
                                <span class="price-value">{{ formatNumber(item.open) }}</span>
                            </div>
                            <div class="price-item high">
                                <span class="price-label">고가</span>
                                <span class="price-value">{{ formatNumber(item.high) }}</span>
                            </div>
                            <div class="price-item low">
                                <span class="price-label">저가</span>
                                <span class="price-value">{{ formatNumber(item.low) }}</span>
                            </div>
                            <div class="price-item close">
                                <span class="price-label">종가</span>
                                <span class="price-value">{{ formatNumber(item.close) }}</span>
                            </div>
                        </div>

                        <!-- 근거 · 조건 (펼치기) -->
                        <button type="button" class="detail-toggle" @click="toggleDetail(item.stock_code)">
                            <span class="arrow" :class="{ open: expandedCard === item.stock_code }">▶</span>
                            근거 · 재무 · 조건 보기
                        </button>

                        <div v-show="expandedCard === item.stock_code" class="detail-panel">
                            <div class="detail-group">
                                <div class="detail-group-title">재무 펀더멘털</div>
                                <div class="detail-row" v-for="row in fundamentalRows(item)" :key="row.label">
                                    <div class="detail-row-name">{{ row.label }}</div>
                                    <div class="detail-row-verdict" :class="row.pass ? 'pass' : (row.pass === false ? 'fail' : 'neutral')">
                                        {{ row.verdict }}
                                    </div>
                                    <div class="detail-row-desc">{{ row.desc }}</div>
                                </div>
                            </div>

                            <div class="detail-group">
                                <div class="detail-group-title">기술적 근거</div>
                                <div class="detail-row" v-for="row in technicalRows(item)" :key="row.label">
                                    <div class="detail-row-name">{{ row.label }}</div>
                                    <div class="detail-row-verdict" :class="row.pass ? 'pass' : 'neutral'">
                                        {{ row.verdict }}
                                    </div>
                                    <div class="detail-row-desc">{{ row.desc }}</div>
                                </div>
                            </div>
                        </div>

                        <!-- 푸터: 기준일 -->
                        <div class="card-footer">
                            <span class="timestamp">{{ formatDate(item.ymd) }} 기준</span>
                        </div>
                    </div>
                </div>

                <div v-else-if="isLoading" class="loader-grid">
                    <div class="skeleton-card" v-for="n in 3" :key="n"></div>
                </div>

                <div v-else class="empty-box">
                    <p>분석된 데이터가 없습니다. 날짜를 변경해 보세요.</p>
                </div>

                <!-- ── 페이지네이션: 3개씩 보여주는 디자인은 유지하되 다음 항목도 탐색 가능 ── -->
                <div v-if="!isLoading && sortedData.length > PAGE_SIZE" class="pagination-bar">
                    <button type="button" class="page-btn" :disabled="currentPage === 0" @click="prevPage">‹ 이전</button>
                    <span class="page-info">{{ currentPage + 1 }} / {{ totalPages }}</span>
                    <button type="button" class="page-btn" :disabled="currentPage >= totalPages - 1" @click="nextPage">다음 ›</button>
                </div>
                </div>
            </section>
        </div>
    </div>
</template>

<script setup>
import CandlestickChart from './common/comp/CandlestickChart.vue';
import aibeesApi from '@scripts/aibeesApi.js';

const router = useRouter();
const title = ref('AIbees Trading');

const goToStockInfo = (stock_code, stock_name) => {
    router.push({ path: '/stock/info', query: { stock_code, stock_name } });
};
const goToChart = (stock_code) => {
    router.push({ path: '/charts/stock', query: { code: stock_code } });
};
const goToBuyTargetDetail = () => {
    router.push({ path: '/stock/buy-target' });
};
const resultData = ref([]);
const isLoading = ref(true);

/* ── 매수타겟 기준일 기본값: 가장 최신 배치 데이터가 있는 날 ──
 * - 배치는 KST 기준 평일 20:00에 완료된다.
 * - 주말(토·일)은 항상 직전 금요일 데이터가 최신이다.
 * - 평일 20:00 이전에는 당일 배치가 아직 안 끝났으므로 직전 영업일 데이터가 최신이다
 *   (월요일 20시 이전이면 일·토를 건너뛰어 금요일까지 거슬러 올라간다).
 * - 평일 20:00 이후에는 당일 데이터가 최신이다.
 * 뷰어의 브라우저 시간대와 무관하게 KST 기준으로 판단해야 하므로 Intl 로 명시적으로 구한다.
 */
const getKstNow = () => {
    const parts = new Intl.DateTimeFormat('en-US', {
        timeZone: 'Asia/Seoul',
        year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', hour12: false, weekday: 'short',
    }).formatToParts(new Date());
    const get = (type) => parts.find(p => p.type === type)?.value;
    const WEEKDAY_NUM = { Sun: 0, Mon: 1, Tue: 2, Wed: 3, Thu: 4, Fri: 5, Sat: 6 };
    return {
        year: Number(get('year')),
        month: Number(get('month')),
        day: Number(get('day')),
        hour: Number(get('hour')) % 24, // 일부 브라우저가 자정을 '24'로 반환하는 것 방어
        weekday: WEEKDAY_NUM[get('weekday')],
    };
};

const toYmdString = (y, m, d) => `${y}-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}`;

const shiftDate = (y, m, d, deltaDays) => {
    const dt = new Date(Date.UTC(y, m - 1, d));
    dt.setUTCDate(dt.getUTCDate() + deltaDays);
    return { year: dt.getUTCFullYear(), month: dt.getUTCMonth() + 1, day: dt.getUTCDate(), weekday: dt.getUTCDay() };
};

const getLatestBatchDate = () => {
    const kst = getKstNow();
    const isWeekend = kst.weekday === 0 || kst.weekday === 6;

    if (!isWeekend && kst.hour >= 20) {
        return toYmdString(kst.year, kst.month, kst.day); // 평일 20시 이후: 오늘
    }

    // 주말이거나 평일 20시 이전: 직전 영업일까지 거슬러 올라간다
    let d = shiftDate(kst.year, kst.month, kst.day, -1);
    while (d.weekday === 0 || d.weekday === 6) {
        d = shiftDate(d.year, d.month, d.day, -1);
    }
    return toYmdString(d.year, d.month, d.day);
};

const selectedDate = ref(getLatestBatchDate());
const dateInput = ref(null);

onMounted(async () => {
    await getStockMainData();
});

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

/* ══════════════ 매수타겟 정렬 (TOP 3 미리보기 — home 은 height 축소가 목적이라
 * 정렬만 바꿀 수 있고 순위번호 역순 표기는 안 씀. 전체 목록/역순은 /stock/buy-target 참고) ══
 */
const SORT_OPTIONS = [
    { key: 'composite_rank_no', label: '종합 순위(신규)', dir: 'asc',  ascLabel: '높은 순위 먼저', descLabel: '낮은 순위 먼저' },
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

const setSortKey = (key) => {
    if (sortKey.value === key) return;
    sortKey.value = key;
    sortDir.value = SORT_OPTIONS.find(o => o.key === key)?.dir ?? 'desc';
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

// home 화면은 높이를 줄이는 게 목적이라 한 번에 3개만 보여준다. 대신 페이지네이션으로
// 다음 항목을 넘겨볼 수 있다. 전체 목록/역순은 "상세보기" → /stock/buy-target 참고.
const PAGE_SIZE = 3;
const currentPage = ref(0);
const totalPages = computed(() => Math.max(1, Math.ceil(sortedData.value.length / PAGE_SIZE)));
const pagedData = computed(() =>
    sortedData.value.slice(currentPage.value * PAGE_SIZE, currentPage.value * PAGE_SIZE + PAGE_SIZE));

const prevPage = () => { if (currentPage.value > 0) currentPage.value -= 1; };
const nextPage = () => { if (currentPage.value < totalPages.value - 1) currentPage.value += 1; };

// 정렬 기준이 바뀌면 첫 페이지로 리셋한다. 날짜 이동은 리셋하지 않는다 — 최우선타겟은
// 서버(전역 1건)에 저장되는 값이라 날짜를 넘나들어도 선택 상태가 유지돼야 한다.
watch([sortKey, sortDir], () => { currentPage.value = 0; });

/* ── 최우선타겟: 사용자가 매수추천 항목 중 하나를 직접 지정 ──
 * 서버(trade_buy_target_priority, 유저당 1건·날짜 무관 전역값)에 저장된다.
 * 다음 영업일 09:00 정규장 매수 라운드에서 worker(BuyExecutor1)가 이 값을 읽어
 * 그 날 매수타겟 1순위로 승격시키고, 라운드가 끝나면(매수 성공·스킵 무관) 1회성으로
 * 초기화한다 — 그래서 프론트도 "선택 즉시 서버에 반영"만 하고 별도 유효기간은 두지 않는다.
 */
const priorityTarget = ref(null);     // 현재 지정된 stock_code (없으면 null)
const priorityTargetName = ref('');   // 위 종목명 — 다른 날짜에서 지정된 경우 select 표시용

const loadPriorityTarget = async () => {
    try {
        const { data } = await aibeesApi.get('/api/v1/stocks/buy-target/priority');
        priorityTarget.value = data?.data?.stock_code ?? null;
        priorityTargetName.value = data?.data?.stock_name ?? '';
    } catch (e) {
        // 비로그인 등으로 조회가 안 돼도 화면 자체는 정상 동작해야 하므로 조용히 무시.
        priorityTarget.value = null;
        priorityTargetName.value = '';
    }
};
onMounted(loadPriorityTarget);

const onPriorityChange = async () => {
    const code = priorityTarget.value;
    const restorePage = currentPage.value;
    try {
        if (!code) {
            await aibeesApi.delete('/api/v1/stocks/buy-target/priority');
            priorityTargetName.value = '';
            return;
        }
        // 서버가 "그 ymd 매수타겟 목록에 실제 존재하는 종목인지"를 검증하므로
        // 지금 화면에 표시 중인 기준일(selectedDate)을 함께 보낸다.
        const ymd = selectedDate.value.replaceAll('-', '');
        const { data } = await aibeesApi.put('/api/v1/stocks/buy-target/priority', { ymd, stock_code: code });
        priorityTargetName.value = data?.data?.stock_name ?? '';
        // 선택한 종목이 몇 번째 페이지에 있는지 찾아 바로 보여준다.
        const idx = sortedData.value.findIndex(i => i.stock_code === code);
        if (idx >= 0) currentPage.value = Math.floor(idx / PAGE_SIZE);
    } catch (e) {
        alert(e?.response?.data?.error?.message || '최우선타겟 저장에 실패했습니다.');
        priorityTarget.value = null;   // 실패했으니 선택 상태를 되돌린다
        currentPage.value = restorePage;
    }
};

/* ── 카드 상세(근거·조건) 펼치기 ── */
const expandedCard = ref(null);
const toggleDetail = (code) => {
    expandedCard.value = expandedCard.value === code ? null : code;
};

/* ── 재무 펀더멘털 판정 (일반적인 가치투자 기준선을 사용한 참고용 해석) ── */
const numOrNull = (v) => {
    if (v === null || v === undefined || v === '') return null;
    const n = Number(v);
    return Number.isNaN(n) ? null : n;
};

const fundamentalRows = (item) => {
    const per = numOrNull(item.per);
    const pbr = numOrNull(item.pbr);
    const roe = numOrNull(item.roe);
    const eps = numOrNull(item.eps);
    const peg = numOrNull(item.peg);

    return [
        {
            label: 'PER',
            pass: per === null ? null : (per > 0 && per <= 15),
            verdict: per === null ? '확인불가' : (per <= 0 ? '적자' : (per <= 15 ? '적합' : '높음')),
            desc: per === null ? '주가수익비율 정보가 없습니다.' : `주가수익비율 ${per}배 · 15배 이하를 저평가 참고 기준으로 봅니다.`,
        },
        {
            label: 'PBR',
            pass: pbr === null ? null : (pbr > 0 && pbr <= 1),
            verdict: pbr === null ? '확인불가' : (pbr <= 0 ? '확인불가' : (pbr <= 1 ? '적합' : '높음')),
            desc: pbr === null ? '주가순자산비율 정보가 없습니다.' : `주가순자산비율 ${pbr}배 · 1배 이하를 저평가 참고 기준으로 봅니다.`,
        },
        {
            label: 'ROE',
            pass: roe === null ? null : roe > 0,
            verdict: roe === null ? '확인불가' : (roe > 0 ? '적합' : '부적합'),
            desc: roe === null ? '자기자본이익률 정보가 없습니다.' : `자기자본이익률 ${roe} · ${roe > 0 ? '이익을 내고 있습니다.' : '손실 상태입니다.'}`,
        },
        {
            label: 'EPS',
            pass: eps === null ? null : eps > 0,
            verdict: eps === null ? '확인불가' : (eps > 0 ? '적합' : '부적합'),
            desc: eps === null ? '주당순이익 정보가 없습니다.' : `주당순이익 ${formatNumber(eps)}원 · ${eps > 0 ? '흑자 기조입니다.' : '적자 상태입니다.'}`,
        },
        {
            label: 'PEG',
            pass: peg === null ? null : (peg > 0 && peg <= 1),
            verdict: peg === null ? '확인불가' : (peg <= 0 ? '확인불가' : (peg <= 1 ? '적합' : '높음')),
            desc: peg === null ? '이익성장 대비 주가 정보가 없습니다.' : `PEG ${peg} · 1 이하를 이익성장 대비 저평가 참고 기준으로 봅니다.`,
        },
    ];
};

/* ── 기술적 근거 판정 (실제 지표 플래그를 그대로 사용, 판정 문구만 서술형으로 변환)
 * 조건 정의는 strategy/kospi1.py, KisStockService.py 계산 로직을 그대로 따름 ── */
const technicalRows = (item) => [
    {
        label: 'MACD 크로스',
        pass: item.macd_cross === 'G',
        verdict: item.macd_cross === 'G' ? '충족' : '미충족',
        desc: item.macd_cross === 'G'
            ? '최근 며칠 내 MACD 선이 시그널선을 상향 돌파(골든크로스)했습니다.'
            : '최근 MACD 골든크로스가 발생하지 않았습니다.',
    },
    {
        label: 'OBV 크로스',
        pass: item.obv_cross === 'G',
        verdict: item.obv_cross === 'G' ? '충족' : '미충족',
        desc: item.obv_cross === 'G'
            ? '거래량 누적지표(OBV)가 최근 며칠 내 9일 이동평균을 상향 돌파했습니다.'
            : '거래량 누적지표(OBV)가 아직 9일 이동평균을 돌파하지 못했습니다.',
    },
    {
        label: '거래제한',
        pass: item.is_vol_limit === 'Y',
        verdict: item.is_vol_limit === 'Y' ? '충족' : '미충족',
        desc: item.is_vol_limit === 'Y'
            ? '오늘 거래량이 최소 거래량 기준선을 넘었습니다.'
            : '오늘 거래량이 최소 거래량 기준선에 못 미칩니다.',
    },
    {
        label: '거래급등',
        pass: item.is_vol_surge === 'Y',
        verdict: item.is_vol_surge === 'Y' ? '충족' : '미충족',
        desc: item.is_vol_surge === 'Y'
            ? '최근 며칠 중 전일 대비 거래량이 급증한 날이 있었습니다.'
            : '최근 전일 대비 거래량 급증이 없었습니다.',
    },
    {
        label: 'BB중심돌파',
        pass: item.is_bb_mid_breakout === 'Y',
        verdict: item.is_bb_mid_breakout === 'Y' ? '충족' : '미충족',
        desc: item.is_bb_mid_breakout === 'Y'
            ? '볼린저밴드 중심선 아래에 있다가 위로 돌파한 뒤 그 위에서 유지되고 있습니다.'
            : '볼린저밴드 중심선 돌파 후 유지 패턴이 확인되지 않았습니다.',
    },
    {
        label: 'BB상단아래',
        pass: item.is_under_bb_upper === 'Y',
        verdict: item.is_under_bb_upper === 'Y' ? '충족' : '미충족',
        desc: item.is_under_bb_upper === 'Y'
            ? '종가가 볼린저밴드 상단선 이하로, 단기 과열(추격 매수 구간)은 아닙니다.'
            : '종가가 볼린저밴드 상단선을 이미 넘어서 단기 과열 구간입니다.',
    },
    {
        label: '중심선위',
        pass: item.is_over_on_mid === 'Y',
        verdict: item.is_over_on_mid === 'Y' ? '충족' : '미충족',
        desc: item.is_over_on_mid === 'Y'
            ? '종가가 20일 이동평균선 위에 있습니다.'
            : '종가가 20일 이동평균선 아래에 있습니다.',
    },
];

const formattedDisplayDate = computed(() => {
    const d = new Date(selectedDate.value);
    return `${d.getFullYear()}.${String(d.getMonth() + 1).padStart(2, '0')}.${String(d.getDate()).padStart(2, '0')}`;
});

const rateClass = (rate) => {
    if (!rate) return '';
    const v = parseFloat(rate);
    if (v > 0) return 'rate-up';
    if (v < 0) return 'rate-down';
    return '';
};

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
            { label: 'MA60',  data: toXY('ma60'),  borderColor: '#d0fe48', type: 'line', pointRadius: 0 },
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

const scoreClass = (score) => {
    if (score === null || score === undefined || score === '') return '';
    const n = Number(score);
    if (Number.isNaN(n)) return '';
    if (n >= 80) return 'score-gold';
    if (n >= 70) return 'score-bronze';
    return '';
};

const formatNumber = (v) => Number(v).toLocaleString();
const formatVolume = (v) => Number(v).toLocaleString();
const formatDate = (v) => v ? `${v.substring(4, 6)}/${v.substring(6, 8)}` : '';
</script>

<style scoped lang="scss">
@use '@@/common.scss' as *;

// 무채색 팔레트(/trade 대시보드와 통일). 기존 변수명은 그대로 두고 값만 회색조로 교체 —
// 아래에서 참조하는 모든 곳(강조색 포함)이 자동으로 무채색이 된다.
$white:   #ffffff;
$gray-50: #fafafa;
$gray-100:#efefef;
$gray-200:#dcdcdc;
$gray-300:#c4c4c4;
$gray-400:#9a9a9a;
$gray-500:#737373;
$gray-700:#3d3d3d;
$gray-900:#141414;
$blue:    #141414;
$navy:    #141414;
$red:     #141414;
$amber:   #141414;
$gold:    #141414;
$bronze:  #3d3d3d;

#home {
    min-height: 100vh;
    background: $gray-50;
    color: $gray-900;
    font-family: 'Pretendard', -apple-system, sans-serif;
}

/* ── 매수타겟 정렬 바 ── */
// 추천종목 섹션 전체를 감싸는 패널 — 제목/정렬/카드가 한 공간에 들어있는 것처럼 보이게 한다.
// 이 아래로 다른 섹션(칼럼 등)이 이어 붙을 예정이라 margin-bottom 으로 다음 섹션과 간격을 둔다.
.reco-section {
    background: $white;
    border: 1px solid $gray-200;
    padding: 20px 20px 16px;
    margin-bottom: 24px;
}

.sort-bar {
    display: flex;
    align-items: center;
    justify-content: left;
    gap: 8px;
    flex-wrap: wrap;
    padding-bottom: 16px;
    margin-bottom: 16px;
    border-bottom: 1px solid $gray-100;

    .sort-label {
        font-size: 0.74rem;
        font-weight: 700;
        color: $gray-400;
        white-space: nowrap;
    }

    .sort-chips {
        display: flex;
        gap: 4px;
        /* 칩이 늘어나면 한 줄에 다 안 들어간다. 부모(.sort-bar)는 flex-wrap 이지만
         * .sort-chips 는 그 안의 flex item 하나라 통째로만 줄바꿈된다 — 안에서
         * 줄바꿈이 안 되면 내재 너비가 화면을 넘겨 버튼이 밖으로 삐져나간다.
         * flex item 기본값인 min-width:auto 때문에 줄어들지도 않으므로 0 으로 푼다. */
        flex-wrap: wrap;
        min-width: 0;
    }

    .sort-chip {
        padding: 5px 12px;
        border: 1px solid $gray-200;
        background: $white;
        color: $gray-500;
        font-size: 0.76rem;
        font-weight: 600;
        cursor: pointer;
        white-space: nowrap;
        transition: border-color .15s, background .15s, color .15s;

        &:hover { border-color: $gray-900; color: $gray-900; }

        &.on {
            border-color: $gray-900;
            background: $gray-900;
            color: $white;
        }
    }

    .sort-dir {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        padding: 5px 11px;
        border: 1px solid $gray-200;
        background: $gray-50;
        color: $gray-700;
        font-size: 0.74rem;
        font-weight: 600;
        cursor: pointer;
        white-space: nowrap;

        &:hover { border-color: $gray-900; color: $gray-900; }

        .dir-arrow {
            font-size: 0.85rem;
            line-height: 1;
            color: $gray-900;
        }
    }
}

.contents {
    max-width: 1040px;
    margin: 0 auto;
    padding: 28px 16px 100px;
}

/* ── Header ── */
.head-desc {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    padding-bottom: 16px;
    margin-bottom: 16px;
    border-bottom: 1px solid $gray-100;
    text-align: start;

    h2 {
        font-size: 1.4rem;
        font-weight: 700;
        margin: 0;
        color: $gray-900;
    }

    @media (max-width: 600px) {
        flex-direction: column;
        align-items: flex-start;
        gap: 12px;
    }
}

/* ── Head Actions ── */
.head-actions {
    display: flex;
    align-items: center;
    gap: 8px;

    @media (max-width: 600px) {
        width: 100%;
    }
}

// 상단 우측 소형 "상세보기" 버튼 — 전체 목록(/stock/buy-target)으로 이동.
.btn-detail {
    padding: 8px 12px;
    border: 1px solid $gray-200;
    background: $white;
    color: $gray-700;
    font-size: 0.8rem;
    font-weight: 700;
    cursor: pointer;
    font-family: inherit;
    white-space: nowrap;
    transition: border-color .15s, color .15s;

    &:hover { border-color: $blue; color: $blue; }
}

/* ── Date Picker ── */
.date-nav {
    display: inline-flex;
    align-items: center;
    gap: 4px;
}

.date-arrow {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    flex-shrink: 0;
    border: 1px solid $gray-200;
    background: $white;
    color: $gray-700;
    font-size: 1rem;
    font-weight: 700;
    line-height: 1;
    cursor: pointer;
    font-family: inherit;
    transition: border-color .15s, color .15s;

    &:hover { border-color: $blue; color: $blue; }
}

.date-picker-trigger {
    position: relative;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 8px 14px;
    border: 1px solid $gray-200;
    background: $white;
    color: $gray-700;
    font-size: 0.88rem;
    font-weight: 600;
    cursor: pointer;
    transition: border-color .15s;

    &:hover { border-color: $blue; }

    .date-value { color: $blue; }

    .hidden-input {
        position: absolute;
        opacity: 0;
        width: 0;
        height: 0;
    }
}

/* ── 최우선타겟 선택 ── */
.priority-bar {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
    padding-bottom: 16px;
    margin-bottom: 16px;
    border-bottom: 1px solid $gray-100;

    .priority-label {
        font-size: 0.74rem;
        font-weight: 700;
        color: $gray-400;
        white-space: nowrap;
    }

    .priority-select {
        flex: 1;
        min-width: 160px;
        max-width: 320px;
        padding: 6px 10px;
        border: 1px solid $gray-200;
        background: $white;
        color: $gray-900;
        font-size: 0.8rem;
        font-weight: 600;
        font-family: inherit;
        cursor: pointer;

        &:hover { border-color: $gray-900; }
    }
}

/* ── 페이지네이션 ── */
.pagination-bar {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 14px;
    margin-top: 4px;

    .page-btn {
        padding: 6px 14px;
        border: 1px solid $gray-200;
        background: $white;
        color: $gray-700;
        font-size: 0.78rem;
        font-weight: 700;
        cursor: pointer;
        font-family: inherit;
        white-space: nowrap;
        transition: border-color .15s, color .15s;

        &:hover:not(:disabled) { border-color: $blue; color: $blue; }

        &:disabled {
            opacity: .4;
            cursor: not-allowed;
        }
    }

    .page-info {
        font-size: 0.78rem;
        font-weight: 700;
        color: $gray-500;
        font-variant-numeric: tabular-nums;
    }
}

/* ── Grid ── */
.signal-grid {
}

/* ── Card ── */
.signal-card {
    background: $white;
    border: 1px solid $gray-200;
    margin-bottom: 16px;
    overflow: hidden;
    transition: border-color .15s;

    &:hover {
        border-color: $gray-900;
    }

    // 사용자가 최우선타겟으로 지정한 종목 — 굵은 테두리로 구분
    &.is-priority {
        border: 2px solid $gray-900;
    }

    /* ── 헤더: 순위 · 종목명/코드 · 액션 버튼 · 금일 변동률 ── */
    .card-head {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 10px 14px 8px;

        .rank-num {
            font-size: 1.2rem;
            font-weight: 800;
            color: $amber;
            line-height: 1;
            flex-shrink: 0;
            font-variant-numeric: tabular-nums;
        }

        .head-main {
            flex: 1;
            min-width: 0;
            display: flex;
            align-items: baseline;
            gap: 6px;

            .name {
                font-size: 0.94rem;
                font-weight: 700;
                margin: 0;
                color: $gray-900;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
                text-align: start;
            }
            .code {
                font-size: 0.72rem;
                color: $gray-500;
                text-align: start;
                white-space: nowrap;
            }

            .priority-badge {
                flex-shrink: 0;
                padding: 2px 7px;
                background: $gray-900;
                color: $white;
                font-size: 0.62rem;
                font-weight: 700;
                white-space: nowrap;
            }
        }

        .actions-row {
            display: flex;
            align-items: center;
            gap: 6px;
            flex-shrink: 0;
        }

        .action-btn {
            padding: 4px 9px;
            font-size: 0.72rem;
            font-weight: 600;
            cursor: pointer;
            border: 1px solid;
            transition: background .12s, color .12s;
            font-family: inherit;
            line-height: 1.4;
            white-space: nowrap;

            &.ai-btn {
                background: $gray-50;
                color: $navy;
                border-color: $gray-300;
                &:hover { background: $gray-200; }
            }

            &.chart-btn {
                background: $white;
                color: $gray-700;
                border-color: $gray-200;
                &:hover { border-color: $blue; color: $blue; background: $gray-50; }
            }
        }

        .rate-badge {
            flex-shrink: 0;
            font-size: 1.05rem;
            font-weight: 800;
            color: $gray-500;
            font-variant-numeric: tabular-nums;
            white-space: nowrap;

            &.rate-up { color: #d92b2b; }
            &.rate-down { color: #2b62d9; }
        }

        @media (max-width: 480px) {
            flex-wrap: wrap;

            .actions-row { order: 3; width: 100%; padding-left: calc(1.2rem + 10px); }
        }
    }

    /* ── 간이 차트: 봉차트 + 이평선, 카드와 같은 너비 (기본 숨김, 차트보기로 토글) ── */
    .mini-chart {
        width: 100%;
        padding: 8px 14px 10px;
        box-sizing: border-box;
        border-top: 1px solid $gray-100;

        .mini-chart-head {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 8px;
            margin-bottom: 6px;
        }

        .mini-legend {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        }

        .leg-item {
            font-size: 0.62rem;
            font-weight: 600;
            color: $gray-500;
            display: flex;
            align-items: center;
            gap: 3px;

            &::before {
                content: '';
                display: inline-block;
                width: 10px;
                height: 2px;
                background: var(--c);
            }
        }

        .mini-chart-detail {
            flex-shrink: 0;
            padding: 2px 8px;
            border: 1px solid $gray-200;
            background: $white;
            color: $gray-700;
            font-size: 0.68rem;
            font-weight: 600;
            cursor: pointer;
            white-space: nowrap;
            font-family: inherit;
            transition: border-color .15s, color .15s;

            &:hover { border-color: $blue; color: $blue; }
        }

        .mini-chart-canvas {
            width: 100%;
            height: 220px;
        }
    }

    /* ── 현재가/거래량/추천 3열 통계 ── */
    .stat-pair {
        display: grid;
        grid-template-columns: 1fr 1fr;
        border-top: 1px solid $gray-100;

        .stat-cell {
            padding: 7px 14px;
            text-align: left;

            &:not(:last-child) { border-right: 1px solid $gray-100; }
        }

        .stat-label {
            display: block;
            font-size: 0.66rem;
            color: $gray-500;
            margin-bottom: 1px;
            text-align: right;
        }

        .stat-main {
            text-align: right;
            font-size: 0.94rem;
            font-weight: 800;
            color: $gray-900;
            line-height: 1.2;

            .unit {
                font-size: 0.68rem;
                font-weight: 600;
                color: $gray-500;
                margin-left: 2px;
            }

            &.score-gold   { color: $gold;   .unit { color: $gold; } }
            &.score-bronze { color: $bronze; .unit { color: $bronze; } }
        }

        .stat-sub {
            font-size: 0.7rem;
            color: $gray-500;
            line-height: 1.3;

            &.rate-up   { color: $red; }
            &.rate-down { color: $navy; }
        }

        &.triple { grid-template-columns: repeat(3, 1fr); }
    }

    /* ── OHLC ── */
    .price-row {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        border-top: 1px solid $gray-100;
        border-bottom: 1px solid $gray-100;
        background: $gray-50;

        .price-item {
            padding: 0.3rem 0.8rem;
            text-align: right;

            &:not(:last-child) { border-right: 1px solid $gray-100; }

            &.high  .price-value { color: $red; }
            &.low   .price-value { color: $navy; }
            &.close .price-value { color: $gray-900; font-weight: 800; }
        }

        .price-label {
            display: block;
            font-size: 0.6rem;
            color: $gray-500;
            margin-bottom: 1px;
        }

        .price-value {
            font-size: 0.76rem;
            font-weight: 600;
            color: $gray-700;
        }
    }

    /* ── 근거 · 조건 펼치기 ── */
    .detail-toggle {
        display: flex;
        align-items: center;
        gap: 6px;
        width: 100%;
        padding: 8px 14px;
        border: none;
        border-top: 1px solid $gray-100;
        background: none;
        color: $gray-500;
        font-family: inherit;
        font-size: 0.74rem;
        font-weight: 600;
        text-align: left;
        cursor: pointer;

        &:hover { color: $blue; }

        .arrow {
            display: inline-block;
            font-size: 0.6rem;
            transition: transform .15s;

            &.open { transform: rotate(90deg); }
        }
    }

    /* ── 근거 상세 패널 ── */
    .detail-panel {
        padding: 4px 14px 12px;
        background: $gray-50;
        text-align: left;

        .detail-group {
            margin-top: 10px;

            &:first-child { margin-top: 0; }
        }

        .detail-group-title {
            font-size: 0.72rem;
            font-weight: 700;
            color: $gray-500;
            margin-bottom: 4px;
        }

        .detail-row {
            display: grid;
            grid-template-columns: 5.5rem 3.5rem 1fr;
            gap: 8px;
            align-items: start;
            padding: 6px 0;
            border-top: 1px solid $gray-100;

            &:first-of-type { border-top: none; }
        }

        .detail-row-name {
            font-size: 0.78rem;
            font-weight: 600;
            color: $gray-900;
        }

        .detail-row-verdict {
            font-size: 0.7rem;
            font-weight: 700;

            &.pass    { color: $navy; }
            &.fail    { color: $red; }
            &.neutral { color: $gray-400; }
        }

        .detail-row-desc {
            font-size: 0.76rem;
            color: $gray-500;
            line-height: 1.4;
        }

        @media (max-width: 480px) {
            .detail-row {
                grid-template-columns: 1fr;
                gap: 2px;
            }
        }
    }

    /* ── Footer ── */
    .card-footer {
        display: flex;
        justify-content: flex-end;
        align-items: center;
        padding: 6px 14px;
        background: $gray-50;
        border-top: 1px solid $gray-100;

        .timestamp {
            font-size: 0.72rem;
            color: $gray-500;
        }
    }
}

/* ── Skeleton ── */
.loader-grid {
    display: grid;
    gap: 16px;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
}

.skeleton-card {
    height: 310px;
    background: $gray-100;
    animation: pulse 1.6s infinite ease-in-out;
}

/* ── Empty ── */
.empty-box {
    text-align: center;
    padding: 80px 0;
    color: $gray-500;
    font-size: 0.9rem;
}

@keyframes pulse {
    0%, 100% { opacity: .5; }
    50%       { opacity: .9; }
}
</style>
