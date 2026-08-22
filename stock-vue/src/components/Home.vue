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
                        <button v-if="isLogin" class="btn-sell-request" @click="goSellRequest">
                            <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none"
                                stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <path d="M3 3v18h18"></path>
                                <path d="m19 9-5 5-4-4-3 3"></path>
                            </svg>
                            매도신호 신청
                        </button>

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
                    <div v-for="(item, index) in sortedData" :key="item.stock_code ?? index" class="signal-card"
                        :class="{ 'super-signal': calculateSignalScore(item) >= 6 }">

                        <div v-if="item.rank_no" class="rank-badge">
                                    <span class="rank-label">RANK</span>
                                    <span class="rank-no">{{ item.rank_no }}</span>
                                </div>
                        <!-- 종목명 + 순위 + 버튼 -->
                        <div class="card-top">
                            <div class="stock-info">
                                <h3 class="name">{{ item.stock_name }}</h3>
                                <span class="code">{{ item.stock_code }}</span>

                            </div>
                            <div class="top-right">
                                <div class="actions-row">
                                    <button class="action-btn ai-btn" @click="goToStockInfo(item.stock_code, item.stock_name)">AI 개요</button>
                                    <button class="action-btn chart-btn" @click="goToChart(item.stock_code)">차트보기</button>
                                    <span class="rate-badge" :class="rateClass(item.rate)">{{ item.rate }}</span>
                                </div>
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

                        <!-- 거래량 + 시그널 + 점수 -->
                        <div class="signal-row">
                            <div class="stat-item">
                                <span class="stat-label">거래량</span>
                                <span class="stat-value">{{ formatVolume(item.volume || 0) }}</span>
                            </div>
                            <div class="stat-item">
                                <span class="stat-label">MACD</span>
                                <span class="stat-value" :class="item.macd_cross === 'G' ? 'val-navy' : 'val-gray'">
                                    {{ item.macd_cross === 'G' ? '골든' : '일반' }}
                                </span>
                            </div>
                            <div class="stat-item">
                                <span class="stat-label">OBV</span>
                                <span class="stat-value" :class="item.obv_cross === 'G' ? 'val-navy' : 'val-gray'">
                                    {{ item.obv_cross === 'G' ? '골든' : '일반' }}
                                </span>
                            </div>
                            <div class="stat-item" v-if="item.score != null">
                                <span class="stat-label">점수</span>
                                <span class="stat-value val-score">{{ item.score }}</span>
                            </div>
                        </div>

                        <!-- 펀더멘털 -->
                        <div class="fundamental-row">
                            <div class="fund-item">
                                <span class="fund-label">PER</span>
                                <span class="fund-value">{{ item.per ?? '-' }}</span>
                            </div>
                            <div class="fund-item">
                                <span class="fund-label">PBR</span>
                                <span class="fund-value">{{ item.pbr ?? '-' }}</span>
                            </div>
                            <div class="fund-item">
                                <span class="fund-label">PEG</span>
                                <span class="fund-value">{{ item.peg ?? '-' }}</span>
                            </div>
                            <div class="fund-item">
                                <span class="fund-label">ROE</span>
                                <span class="fund-value">{{ item.roe ?? '-' }}</span>
                            </div>
                            <div class="fund-item">
                                <span class="fund-label">EPS</span>
                                <span class="fund-value">{{ item.eps ? formatNumber(item.eps) : '-' }}</span>
                            </div>
                        </div>

                        <!-- 기술적 조건 칩 -->
                        <div class="chip-row">
                            <span :class="['chip', { on: item.is_vol_limit === 'Y' }]">거래제한</span>
                            <span :class="['chip', { on: item.is_vol_surge === 'Y' }]">거래급등</span>
                            <span :class="['chip', { on: item.is_bb_mid_breakout === 'Y' }]">BB중심돌파</span>
                            <span :class="['chip', { on: item.is_under_bb_upper === 'Y' }]">BB상단아래</span>
                            <span :class="['chip', { on: item.is_over_on_mid === 'Y' }]">중심선위</span>
                        </div>

                        <div class="card-footer">
                            <span class="action-type">{{ item.action_type }}</span>
                            <span class="timestamp">{{ formatDate(item.ymd) }}</span>
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

const calculateSignalScore = (item) => {
    let s = (item.macd_cross === 'G' ? 1 : 0) + (item.obv_cross === 'G' ? 1 : 0);
    ['is_vol_limit', 'is_vol_surge', 'is_bb_mid_breakout', 'is_under_bb_upper', 'is_over_on_mid'].forEach(p => {
        if (item[p] === 'Y') s++;
    });
    return s;
};

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

const formatNumber = (v) => Number(v).toLocaleString();
const formatVolume = (v) => Number(v).toLocaleString();
const formatDate = (v) => v ? `${v.substring(4, 6)}/${v.substring(6, 8)}` : '';
</script>

<style scoped lang="scss">
$white:   #ffffff;
$gray-50: #f8f9fa;
$gray-100:#ebebeb;
$gray-200:#d0d0d0;
$gray-400:#909090;
$gray-500:#6b6b6b;
$gray-700:#333333;
$gray-900:#111111;
$blue:    #1971c2;
$navy:    #1c3d6e;
$red:     #c92a2a;
$amber:   #e67700;

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
    border: 1px solid $gray-100;
    border-radius: 12px;

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
        border-radius: 999px;
        background: $white;
        color: $gray-500;
        font-size: 0.76rem;
        font-weight: 600;
        cursor: pointer;
        white-space: nowrap;
        transition: border-color .15s, background .15s, color .15s;

        &:hover { border-color: $blue; color: $blue; }

        &.on {
            border-color: $blue;
            background: #e7f0fd;
            color: $blue;
        }
    }

    .sort-dir {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        padding: 5px 11px;
        border: 1px solid $gray-200;
        border-radius: 999px;
        background: $gray-50;
        color: $gray-700;
        font-size: 0.74rem;
        font-weight: 600;
        cursor: pointer;
        white-space: nowrap;

        &:hover { border-color: $blue; color: $blue; }

        .dir-arrow {
            font-size: 0.85rem;
            line-height: 1;
            color: $blue;
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
    border-radius: 0.5rem;
    font-size: 0.86rem;
    font-weight: 700;
    cursor: pointer;
    font-family: inherit;
    white-space: nowrap;
    box-shadow: 0 1px 3px rgba(0, 0, 0, .1);
    transition: background .15s;

    &:hover { background: darken(#1c3d6e, 6%); }
}

/* ── Date Picker ── */
.date-picker-trigger {
    position: relative;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 8px 14px;
    border: 1px solid $gray-200;
    border-radius: 0.5rem;
    background: $white;
    color: $gray-700;
    font-size: 0.88rem;
    font-weight: 600;
    cursor: pointer;
    box-shadow: 0 1px 3px rgba(0,0,0,.06);
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
    display: grid;
    gap: 16px;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
}

/* ── Card ── */
.signal-card {
    background: $white;
    border: 1px solid $gray-200;
    border-radius: 0.6rem;
    overflow: hidden;
    transition: box-shadow .15s;

    &:hover {
        box-shadow: 0 4px 16px rgba(0,0,0,.08);
    }

    &.super-signal {
        border-color: $amber;

        .rank-badge {
            background: $amber;
        }
    }


    /* ── Rank Badge ── */
    .rank-badge {
        display: flex;
        flex-direction: row;
        align-items: center;
        justify-content: center;
        background: $navy;
        border-top-left-radius: 0.4rem;
        border-top-right-radius: 0.4rem;
        padding: 3px 10px 4px;
        min-width: 44px;

        .rank-label {
            font-size: 0.7rem;
            font-weight: 700;
            color: rgba(255, 255, 255, 0.6);
            letter-spacing: 0.08em;
            line-height: 1;
            margin-right: 0.5rem
        }

        .rank-no {
            font-size: 1rem;
            font-weight: 800;
            color: $white;
            line-height: 1.1;
        }
    }

    /* ── Card Top ── */
    .card-top {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 14px 14px 10px;
        gap: 10px;

        .stock-info {
            flex: 1;
            min-width: 0;

            .name {
                font-size: 1.05rem;
                font-weight: 700;
                margin: 0 0 2px;
                color: $gray-900;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }
            .code {
                font-size: 0.78rem;
                color: $gray-500;
            }
        }

        .top-right {
            display: flex;
            flex-direction: column;
            align-items: flex-end;
            gap: 6px;
            flex-shrink: 0;
        }


        .actions-row {
            display: flex;
            align-items: center;
            gap: 6px;
        }

        .action-btn {
            padding: 4px 9px;
            border-radius: 0.3rem;
            font-size: 0.72rem;
            font-weight: 600;
            cursor: pointer;
            border: 1px solid;
            transition: background .12s, color .12s;
            font-family: inherit;
            line-height: 1.4;

            &.ai-btn {
                background: #f0f4ff;
                color: $navy;
                border-color: #bac8ff;
                &:hover { background: #dbe4ff; }
            }

            &.chart-btn {
                background: $white;
                color: $gray-700;
                border-color: $gray-200;
                &:hover { border-color: $blue; color: $blue; background: $gray-50; }
            }
        }
    }

    .rate-badge {
        font-size: 0.8rem;
        font-weight: 700;
        padding: 4px 8px;
        border-radius: 0.3rem;
        background: $gray-100;
        color: $gray-500;

        &.rate-up   { background: #ffe3e3; color: $red; }
        &.rate-down { background: #dbe4ff; color: $navy; }
    }

    /* ── OHLC ── */
    .price-row {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        border-top: 1px solid $gray-200;
        border-bottom: 1px solid $gray-200;
        background: $gray-50;

        .price-item {
            padding: 8px 0;
            text-align: center;

            &:not(:last-child) { border-right: 1px solid $gray-200; }

            &.high  .price-value { color: $red; }
            &.low   .price-value { color: $navy; }
            &.close .price-value { color: $gray-900; font-weight: 800; }
        }

        .price-label {
            display: block;
            font-size: 0.65rem;
            color: $gray-500;
            margin-bottom: 3px;
        }

        .price-value {
            font-size: 0.84rem;
            font-weight: 600;
            color: $gray-700;
        }
    }

    /* ── 거래량 + 시그널 ── */
    .signal-row {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(60px, 1fr));
        border-bottom: 1px solid $gray-200;

        .stat-item {
            padding: 9px 0;
            text-align: center;

            &:not(:last-child) { border-right: 1px solid $gray-200; }
        }

        .stat-label {
            display: block;
            font-size: 0.65rem;
            color: $gray-500;
            margin-bottom: 3px;
        }

        .stat-value {
            font-size: 0.85rem;
            font-weight: 700;
            color: $gray-900;

            &.val-navy  { color: $navy; }
            &.val-gray  { color: $gray-400; }
            &.val-score { color: $amber; font-size: 1rem; }
        }
    }

    /* ── 펀더멘털 ── */
    .fundamental-row {
        display: grid;
        grid-template-columns: repeat(5, 1fr);
        border-bottom: 1px solid $gray-200;
        background: $gray-50;

        .fund-item {
            padding: 8px 0;
            text-align: center;

            &:not(:last-child) { border-right: 1px solid $gray-200; }
        }

        .fund-label {
            display: block;
            font-size: 0.62rem;
            color: $gray-500;
            font-weight: 600;
            margin-bottom: 3px;
        }

        .fund-value {
            font-size: 0.82rem;
            font-weight: 700;
            color: $gray-700;
        }
    }

    /* ── Chips ── */
    .chip-row {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        padding: 10px 16px;

        .chip {
            font-size: 0.72rem;
            font-weight: 600;
            padding: 3px 9px;
            border-radius: 0.3rem;
            background: $gray-100;
            color: $gray-500;
            border: 1px solid $gray-200;

            &.on {
                background: #dbe4ff;
                color: $navy;
                border-color: #bac8ff;
            }
        }
    }

    /* ── Footer ── */
    .card-footer {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 10px 16px;
        background: $gray-50;
        border-top: 1px solid $gray-100;

        .action-type {
            font-size: 0.78rem;
            font-weight: 700;
            color: $red;
            text-transform: uppercase;
        }

        .timestamp {
            font-size: 0.78rem;
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
    background: $gray-200;
    border-radius: 0.6rem;
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
