<template>
    <div id="home">
        <Headers :prop_title="title" />

        <div class="contents">
            <!-- ── Tab Nav ── -->
            <nav class="tab-nav">
                <button class="tab-btn" :class="{ active: activeTab === 'buy' }" @click="activeTab = 'buy'">
                    매수타겟
                </button>
                <button class="tab-btn" :class="{ active: activeTab === 'sell' }" @click="activeTab = 'sell'">
                    매도신호
                </button>
            </nav>

            <!-- ════════ 매수타겟 탭 ════════ -->
            <div v-show="activeTab === 'buy'" class="tab-panel">
                <section class="head-desc">
                    <div class="head-left">
                        <h2>전략매수 포착 현황</h2>
                        <p class="sub-text">일간 지표로 계산한 기술적 타점</p>
                    </div>

                    <div class="head-actions">
                        <!-- <button v-if="isLogin" class="btn-sell-request" @click="goSellRequest">
                            <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none"
                                stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <path d="M3 3v18h18"></path>
                                <path d="m19 9-5 5-4-4-3 3"></path>
                            </svg>
                            매도신호 신청
                        </button> -->

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
                    </div>
                </section>

                <!-- ── 정렬 옵션 ── -->
                <section v-if="!isLoading && resultData.length > 0" class="sort-bar">
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
                    <span class="sort-count">{{ sortedData.length }}종목</span>
                </section>

                <section class="buy-target">
                    <div v-if="!isLoading && sortedData.length > 0" class="signal-grid">
                        <div v-for="(item, index) in sortedData" :key="item.stock_code ?? index" class="signal-card">

                            <!-- 헤더: 순위 + 종목명/코드 + 액션 버튼 + 즐겨찾기 -->
                            <div class="card-head">
                                <div class="rank-num">{{ String(item.rank_no ?? index + 1).padStart(2, '0') }}</div>
                                <div class="head-main">
                                    <h3 class="name">{{ item.stock_name }}</h3>
                                    <div class="code">{{ item.stock_code }}</div>
                                </div>
                                <div class="actions-row">
                                    <button class="action-btn ai-btn" @click="goToStockInfo(item.stock_code, item.stock_name)">AI 개요</button>
                                    <button class="action-btn chart-btn" @click="goToChart(item.stock_code)">차트보기</button>
                                </div>
                                <button type="button" class="star-btn" :class="{ on: isFavorite(item.stock_code) }"
                                        @click="toggleFavorite(item.stock_code)" title="관심종목">
                                    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24"
                                        :fill="isFavorite(item.stock_code) ? 'currentColor' : 'none'" stroke="currentColor"
                                        stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                        <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon>
                                    </svg>
                                </button>
                            </div>

                            <!-- 현재가 + 거래량 + 추천 -->
                            <div class="stat-pair triple">
                                <div class="stat-cell">
                                    <span class="stat-label">현재가</span>
                                    <div class="stat-main">{{ formatNumber(item.close) }}<span class="unit">원</span></div>
                                    <div class="stat-sub" :class="rateClass(item.rate)">{{ item.rate ?? '-' }}</div>
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
                        <div class="skeleton-card" v-for="n in 4" :key="n"></div>
                    </div>

                    <div v-else class="empty-box">
                        <p>분석된 데이터가 없습니다. 날짜를 변경해 보세요.</p>
                    </div>
                </section>
            </div>

            <!-- ════════ 매도신호 탭 ════════ -->
            <div v-show="activeTab === 'sell'" class="tab-panel">
                <!-- 비로그인: 안내 문구 -->
                <div v-if="!isLogin" class="login-required">
                    <p>로그인 후 사용 가능합니다</p>
                </div>

                <!-- 로그인: 매도신호 조회 -->
                <template v-else>
                    <section class="head-desc">
                        <div class="head-left">
                            <h2>매도신호 현황</h2>
                            <p class="sub-text">보유 종목의 청산 시그널</p>
                        </div>

                        <div class="head-actions">
                            <div class="date-picker-trigger" @click="openSellDatePicker">
                                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"
                                    fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"
                                    stroke-linejoin="round">
                                    <rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect>
                                    <line x1="16" y1="2" x2="16" y2="6"></line>
                                    <line x1="8" y1="2" x2="8" y2="6"></line>
                                    <line x1="3" y1="10" x2="21" y2="10"></line>
                                </svg>
                                <span class="date-value">{{ formattedSellDisplayDate }}</span>
                                <input type="date" ref="sellDateInput" class="hidden-input" v-model="sellSelectedDate"
                                    @change="handleSellDateChange" />
                            </div>
                        </div>
                    </section>

                    <section class="sell-signal">
                        <div v-if="!isSellLoading && sellData.length > 0" class="signal-grid">
                            <!-- TODO: 매도신호 카드 (매수타겟과 동일한 카드 형태, 구체 항목 추후 정의) -->
                        </div>

                        <div v-else-if="isSellLoading" class="loader-grid">
                            <div class="skeleton-card" v-for="n in 4" :key="n"></div>
                        </div>

                        <div v-else class="empty-box">
                            <p>조회된 매도신호가 없습니다.</p>
                        </div>
                    </section>
                </template>
            </div>
        </div>
    </div>
</template>

<script setup>
import Lnb from './common/Lnb.vue';
import aibeesApi from '@scripts/aibeesApi.js';
import { assUserSession } from '@scripts/stores/user-stores';

const router = useRouter();
const title = ref('SSAP');

const userSession = assUserSession();
const isLogin = ref(false);

const activeTab = ref('buy');

const goSellRequest = () => router.push({ path: '/sell-request' });

const goToStockInfo = (stock_code, stock_name) => {
    router.push({ path: '/stock/info', query: { stock_code, stock_name } });
};
const goToChart = (stock_code) => {
    router.push({ path: '/charts/stock', query: { code: stock_code } });
};
const resultData = ref([]);
const isLoading = ref(true);
const selectedDate = ref(new Date().toISOString().slice(0, 10));
const dateInput = ref(null);

onMounted(async () => {
    isLogin.value = userSession.isUserSession();
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

/* ══════════════ 매수타겟 정렬 ══════════════
 * 조회는 하루치 전체를 한 번에 받아오므로 클라이언트에서 정렬한다(재조회 없음).
 *
 * 규칙은 worker(trade_worker/repository.py _ORDER_FIELDS)와 맞춘다:
 *   · 필드별 기본 방향 — rank_no 는 작을수록 상위(asc), score/volume 은 클수록 상위(desc)
 *   · 값이 없는(null) 종목은 정렬 방향과 무관하게 항상 뒤
 *   · 전부 동점이면 stock_code 로 최종 결정 (매 조회마다 순서가 흔들리지 않도록)
 */
const SORT_OPTIONS = [
    { key: 'rank_no', label: '추천순위', dir: 'asc', ascLabel: '높은 순위 먼저', descLabel: '낮은 순위 먼저' },
    { key: 'score',   label: '점수',     dir: 'desc', ascLabel: '낮은 점수 먼저', descLabel: '높은 점수 먼저' },
    { key: 'volume',  label: '거래량',   dir: 'desc', ascLabel: '적은 순',        descLabel: '많은 순' },
];

const sortKey = ref('rank_no');
const sortDir = ref('asc');

const currentSort = computed(
    () => SORT_OPTIONS.find(o => o.key === sortKey.value) ?? SORT_OPTIONS[0]);

// 기준을 바꾸면 그 필드의 기본 방향으로 되돌린다.
// (거래량을 고르고 '적은 순'이 남아 있으면 의도와 반대 결과가 나온다)
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

/* ── 매도신호 탭 ── */
const sellData = ref([]);
const isSellLoading = ref(false);
const sellSelectedDate = ref(new Date().toISOString().slice(0, 10));
const sellDateInput = ref(null);

const getSellSignalData = async () => {
    if (!isLogin.value) return;
    isSellLoading.value = true;
    try {
        // TODO: 매도신호 조회 API 연동 (구체 스펙 추후 정의)
        sellData.value = [];
    } catch (e) {
        console.error(e);
    } finally {
        isSellLoading.value = false;
    }
};

const handleSellDateChange = () => getSellSignalData();
const openSellDatePicker = () => sellDateInput.value?.showPicker();

const formattedSellDisplayDate = computed(() => {
    const d = new Date(sellSelectedDate.value);
    return `${d.getFullYear()}.${String(d.getMonth() + 1).padStart(2, '0')}.${String(d.getDate()).padStart(2, '0')}`;
});

// 매도신호 탭 최초 진입 시 1회 로드
watch(activeTab, (tab) => {
    if (tab === 'sell' && isLogin.value && sellData.value.length === 0) {
        getSellSignalData();
    }
});

/* ── 관심종목 (로컬 저장, 서버 연동 없음) ── */
const FAVORITE_KEY = 'ssap_favorite_stocks';
const favoriteStocks = ref(new Set());
try {
    const saved = JSON.parse(localStorage.getItem(FAVORITE_KEY) || '[]');
    favoriteStocks.value = new Set(saved);
} catch (e) { /* ignore malformed storage */ }

const isFavorite = (code) => favoriteStocks.value.has(code);
const toggleFavorite = (code) => {
    const next = new Set(favoriteStocks.value);
    next.has(code) ? next.delete(code) : next.add(code);
    favoriteStocks.value = next;
    localStorage.setItem(FAVORITE_KEY, JSON.stringify([...next]));
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
.sort-bar {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
    padding: 10px 12px;
    margin-bottom: 12px;
    background: $white;
    border: 1px solid $gray-200;

    .sort-label {
        font-size: 0.74rem;
        font-weight: 700;
        color: $gray-400;
        white-space: nowrap;
    }

    .sort-chips {
        display: flex;
        gap: 4px;
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

    .sort-count {
        margin-left: auto;
        font-size: 0.72rem;
        color: $gray-400;
        white-space: nowrap;
    }
}

@media (max-width: 560px) {
    .sort-bar {
        .sort-count { margin-left: 0; width: 100%; }
    }
}

.contents {
    max-width: 1040px;
    margin: 0 auto;
    padding: 28px 16px 100px;
}

/* ── Tab Nav ── */
.tab-nav {
    display: flex;
    gap: 4px;
    border-bottom: 2px solid $gray-200;
    margin-bottom: 24px;

    .tab-btn {
        position: relative;
        padding: 11px 20px;
        background: none;
        border: none;
        font-family: inherit;
        font-size: 0.95rem;
        font-weight: 700;
        color: $gray-400;
        cursor: pointer;
        transition: color .15s;

        &::after {
            content: '';
            position: absolute;
            left: 0;
            right: 0;
            bottom: -2px;
            height: 2px;
            background: $navy;
            transform: scaleX(0);
            transition: transform .18s ease;
        }

        &:hover { color: $gray-700; }

        &.active {
            color: $navy;
            &::after { transform: scaleX(1); }
        }
    }
}

/* ── Login Required (매도신호) ── */
.login-required {
    text-align: center;
    padding: 100px 0;
    color: $gray-500;
    font-size: 1rem;
    font-weight: 600;
}

/* ── Header ── */
.head-desc {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    margin-bottom: 24px;

    h2 {
        font-size: 1.4rem;
        font-weight: 700;
        margin: 0;
        color: $gray-900;
    }

    .sub-text {
        font-size: 0.82rem;
        color: $gray-500;
        margin: 4px 0 0;
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
    gap: 10px;

    @media (max-width: 600px) {
        width: 100%;
    }
}

.btn-sell-request {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 8px 14px;
    background: $navy;
    color: $white;
    border: none;
    font-size: 0.86rem;
    font-weight: 700;
    cursor: pointer;
    font-family: inherit;
    white-space: nowrap;
    transition: background .15s;

    &:hover { background: #000000; }
}

/* ── Date Picker ── */
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

/* ── Grid ── */
.signal-grid {
    // display: grid;
    // gap: 16px;
    // grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
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

    /* ── 헤더: 순위 · 종목명/코드 · 액션 버튼 · 즐겨찾기 ── */
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

        .star-btn {
            display: flex;
            align-items: center;
            justify-content: center;
            width: 26px;
            height: 26px;
            flex-shrink: 0;
            padding: 0;
            border: none;
            background: none;
            color: $gray-200;
            cursor: pointer;
            transition: color .15s, transform .1s;

            &:hover { color: $gray-400; }
            &:active { transform: scale(0.9); }
            &.on { color: $amber; }
        }

        @media (max-width: 480px) {
            flex-wrap: wrap;

            .actions-row { order: 3; width: 100%; padding-left: calc(1.2rem + 10px); }
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
        }

        .stat-main {
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
            padding: 5px 0;
            text-align: center;

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
