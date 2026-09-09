<template>
    <div id="trade-dashboard">
        <Headers :prop_title="title" />

        <div class="contents">
            <!-- ── 하위 메뉴 바로가기 ── -->
            <section class="menu-grid" v-if="tradeChildren.length">
                <div
                    v-for="c in tradeChildren" :key="c.menu_code"
                    class="menu-tile"
                    @click="goPath(childPath(c))"
                >
                    <span class="menu-label">{{ c.menu_title || c.menu_name }}</span>
                    <span class="menu-arrow">&rarr;</span>
                </div>
            </section>
            <section v-else class="menu-grid-empty">
                <p>등록된 하위 메뉴가 없습니다.</p>
            </section>

            <!-- ── 요약 대시보드 ── -->
            <section class="summary-grid">

                <!-- 자산현황 -->
                <article class="d-card">
                    <header class="d-card-head">
                        <h3>자산현황</h3>
                        <button v-if="assetLink" class="d-link" @click="goPath(assetLink)">자세히</button>
                    </header>

                    <div v-if="loadingAccount" class="d-skel"></div>
                    <div v-else-if="!account" class="d-empty">데이터를 불러올 수 없습니다.</div>
                    <div v-else class="d-body">
                        <div class="d-figure">
                            <span class="d-num">{{ fmtWon(account.total_asset) }}</span>
                            <span class="d-unit">원</span>
                        </div>
                        <dl class="d-rows">
                            <div class="d-row"><dt>예수금</dt><dd>{{ fmtWon(account.user_balance) }}원</dd></div>
                            <div class="d-row"><dt>주식평가액</dt><dd>{{ fmtWon(account.stock_amount) }}원</dd></div>
                        </dl>
                    </div>
                </article>

                <!-- 보유종목 -->
                <article class="d-card">
                    <header class="d-card-head">
                        <h3>보유종목</h3>
                        <button v-if="assetLink" class="d-link" @click="goPath(assetLink)">자세히</button>
                    </header>

                    <div v-if="loadingPortfolio" class="d-skel"></div>
                    <div v-else-if="!holdings.length" class="d-empty">보유 종목이 없습니다.</div>
                    <div v-else class="d-body">
                        <div class="d-figure">
                            <span class="d-num">{{ holdings.length }}</span>
                            <span class="d-unit">종목</span>
                        </div>
                        <ul class="d-list">
                            <li v-for="h in holdings.slice(0, 3)" :key="h.stock_code">
                                <span class="d-list-name">{{ h.stock_name }}</span>
                                <span class="d-list-val">{{ fmtSigned(h.profit) }}</span>
                            </li>
                        </ul>
                        <p v-if="holdings.length > 3" class="d-more">외 {{ holdings.length - 3 }}종목</p>
                    </div>
                </article>

                <!-- 매수 / 매도 정책 요약 -->
                <article class="d-card">
                    <header class="d-card-head">
                        <h3>매수 · 매도 정책</h3>
                        <button v-if="buyLink" class="d-link" @click="goPath(buyLink)">자세히</button>
                    </header>

                    <div v-if="loadingOptions" class="d-skel"></div>
                    <div v-else-if="!options" class="d-empty">데이터를 불러올 수 없습니다.</div>
                    <dl v-else class="d-rows">
                        <div class="d-row"><dt>손절</dt><dd>-{{ pct(options.s1_stop_loss_pct, 0.05) }}%</dd></div>
                        <div class="d-row"><dt>익절</dt><dd>+{{ pct(options.s1_take_profit_pct, 0.30) }}%</dd></div>
                        <div class="d-row"><dt>트레일링</dt><dd>{{ bool(options.s1_use_trailing, 1) ? '사용' : '미사용' }}</dd></div>
                        <div class="d-row"><dt>보유 한도</dt><dd>{{ options.s1_max_hold_bars ?? 12 }}봉</dd></div>
                        <div class="d-row"><dt>RSI 신뢰구간</dt><dd>{{ options.s1_rsi_ideal_low ?? 40 }} ~ {{ options.s1_rsi_ideal_high ?? 65 }}</dd></div>
                        <div class="d-row"><dt>진입 필터</dt><dd>{{ enabledFilterCount }} / {{ FILTER_KEYS.length }} 사용</dd></div>
                    </dl>
                </article>

                <!-- Worker mode -->
                <article class="d-card">
                    <header class="d-card-head">
                        <h3>Worker Mode</h3>
                        <button v-if="workerLink" class="d-link" @click="goPath(workerLink)">자세히</button>
                    </header>

                    <div v-if="loadingWorker" class="d-skel"></div>
                    <div v-else-if="!workerState" class="d-empty">데이터를 불러올 수 없습니다.</div>
                    <div v-else class="d-body">
                        <div class="d-status" :class="{ on: workerState.enabled_flag === 'Y' }">
                            <span class="d-dot"></span>
                            {{ workerState.enabled_flag === 'Y' ? '운용 중' : '정지' }}
                        </div>
                        <dl class="d-rows">
                            <div class="d-row"><dt>활성 모드</dt><dd>{{ activeModeName }}</dd></div>
                            <div class="d-row"><dt>상태</dt><dd>{{ RUN_STATE_LABEL[workerState.run_state] || workerState.run_state }}</dd></div>
                            <div class="d-row" v-if="workerState.pending_mode"><dt>전환 예약</dt><dd>{{ pendingModeName }}</dd></div>
                        </dl>
                        <p v-if="workerState.last_message" class="d-msg">{{ workerState.last_message }}</p>
                    </div>
                </article>

            </section>
        </div>
    </div>
</template>

<script setup>
import aibeesApi from '@scripts/aibeesApi.js';
import { assUserSession } from '@scripts/stores/user-stores';
import { fetchModes, fetchState, RUN_STATE_LABEL } from '@scripts/useAutoTrade.js';

const router = useRouter();
const userSession = assUserSession();
const title = '트레이딩 대시보드';

const userId = computed(() => userSession.user?.loginInfo?.user_id);
const isAdmin = computed(() => {
    const roles = userSession.getRole ?? [];
    return roles.some(r => r.toUpperCase() === 'ADMIN' || r === '시스템 관리자');
});

const goPath = (path) => router.push({ path });

/* ── 하위 메뉴(=/trade 의 자식 메뉴) 링크 ── */
const allMenu = ref([]);

// menu_path 는 최상위 항목엔 '/trade'처럼 선행 슬래시가 붙어 오고,
// 자식 항목은 어떤 규칙인지 보장이 없어 항상 정규화해서 비교/조합한다.
const norm = (p) => String(p ?? '').replace(/^\/+/, '').replace(/\/+$/, '');

const tradeMenu = computed(() => allMenu.value.find(m => norm(m.menu_path) === 'trade'));

const tradeChildren = computed(() => {
    const m = tradeMenu.value;
    if (!m) return [];
    return (m.children ?? [])
        .filter(c => c.display_flag !== 'N' && c.enabled_flag !== 'N')
        .filter(c => c.admin_only !== 'Y' || isAdmin.value)
        .sort((a, b) => (a.sort ?? 0) - (b.sort ?? 0));
});

const childPath = (c) => `/${norm(tradeMenu.value?.menu_path)}/${norm(c.menu_path)}`;

/* 전체 메뉴 트리에서 컴포넌트명으로 실제 경로를 찾는다(카드의 "자세히" 링크용).
 * 컴포넌트가 /trade 밖(예: /auto-trade)에 등록돼 있어도 정확히 찾아간다. */
const findMenuPath = (componentName) => {
    for (const top of allMenu.value) {
        if (top.menu_component === componentName) return `/${norm(top.menu_path)}`;
        for (const c of (top.children ?? [])) {
            if (c.menu_component === componentName) return `/${norm(top.menu_path)}/${norm(c.menu_path)}`;
        }
    }
    return null;
};

const assetLink  = computed(() => findMenuPath('MyWallet'));
const buyLink    = computed(() => findMenuPath('BuySetting'));
const workerLink = computed(() => findMenuPath('ModeSetting') || findMenuPath('RunStatus'));

/* ── 자산현황 / 보유종목 ── */
const account  = ref(null);
const holdings = ref([]);
const loadingAccount   = ref(true);
const loadingPortfolio = ref(true);

const fetchAccount = async () => {
    if (!userId.value) { loadingAccount.value = false; return; }
    try {
        const { data } = await aibeesApi.get(`/api/v1/users/${userId.value}/account`);
        account.value = data ?? null;
    } catch (e) {
        console.error('[TradeDashboard] 계좌 조회 실패', e);
        account.value = null;
    } finally {
        loadingAccount.value = false;
    }
};

const fetchPortfolio = async () => {
    if (!userId.value) { loadingPortfolio.value = false; return; }
    try {
        const { data } = await aibeesApi.get(`/api/v1/users/${userId.value}/portfolio`);
        holdings.value = data?.holdings ?? [];
    } catch (e) {
        console.error('[TradeDashboard] 포트폴리오 조회 실패', e);
        holdings.value = [];
    } finally {
        loadingPortfolio.value = false;
    }
};

/* ── 매수 / 매도 정책 요약 ── */
const options = ref(null);
const loadingOptions = ref(true);

const FILTER_KEYS = [
    's1_enable_macd_filter', 's1_enable_rsi_filter', 's1_enable_bb_upper_filter',
    's1_enable_vol_avg_filter', 's1_enable_regime_gate',
];
const enabledFilterCount = computed(() => {
    if (!options.value) return 0;
    return FILTER_KEYS.filter(k => Number(options.value[k] ?? 1) === 1).length;
});

const fetchOptions = async () => {
    try {
        const { data } = await aibeesApi.get('/api/v1/strategy/options');
        options.value = data.data ?? null;
    } catch (e) {
        console.error('[TradeDashboard] 전략 옵션 조회 실패', e);
        options.value = null;
    } finally {
        loadingOptions.value = false;
    }
};

const pct  = (v, def) => (Number(v ?? def) * 100).toFixed(1).replace(/\.0$/, '');
const bool = (v, def) => Number(v ?? def) === 1;

/* ── Worker mode ── */
const workerState  = ref(null);
const modes        = ref([]);
const loadingWorker = ref(true);

const fetchWorker = async () => {
    try {
        const [state, modeList] = await Promise.all([fetchState(), fetchModes()]);
        workerState.value = state;
        modes.value = modeList ?? [];
    } catch (e) {
        console.error('[TradeDashboard] worker 상태 조회 실패', e);
        workerState.value = null;
    } finally {
        loadingWorker.value = false;
    }
};

const modeName = (code) => modes.value.find(m => m.mode_code === code)?.mode_name ?? code ?? '-';
const activeModeName  = computed(() => modeName(workerState.value?.active_mode));
const pendingModeName = computed(() => modeName(workerState.value?.pending_mode));

/* ── 포맷 헬퍼 ── */
const toNum = (v) => (v === null || v === undefined || v === '') ? null : Number(v);
const fmtWon = (v) => {
    const n = toNum(v);
    return n === null || Number.isNaN(n) ? '-' : n.toLocaleString(undefined, { maximumFractionDigits: 0 });
};
const fmtSigned = (v) => {
    const n = toNum(v);
    if (n === null || Number.isNaN(n)) return '-';
    const s = n.toLocaleString(undefined, { maximumFractionDigits: 0 });
    return n > 0 ? `+${s}` : s;
};

onMounted(() => {
    allMenu.value = userSession.loadMenuList() ?? [];
    fetchAccount();
    fetchPortfolio();
    fetchOptions();
    fetchWorker();
});
</script>

<style scoped lang="scss">
/* ── 무채색 팔레트 ── */
$white:    #ffffff;
$gray-50:  #fafafa;
$gray-100: #efefef;
$gray-200: #dcdcdc;
$gray-300: #c4c4c4;
$gray-400: #9a9a9a;
$gray-500: #737373;
$gray-700: #3d3d3d;
$gray-900: #141414;
$black:    #000000;

#trade-dashboard {
    min-height: 100vh;
    background: $white;
    color: $gray-900;
    font-family: 'Pretendard', -apple-system, sans-serif;
}

.contents {
    max-width: 1100px;
    margin: 0 auto;
    padding: 24px 16px 100px;
}

/* ── 하위 메뉴 그리드 ── */
.menu-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
    gap: 1px;
    background: $gray-200;
    border: 1px solid $gray-200;
    margin-bottom: 20px;
}

.menu-tile {
    background: $white;
    padding: 18px 16px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    cursor: pointer;
    transition: background .12s;

    .menu-label {
        font-size: 0.88rem;
        font-weight: 700;
        color: $gray-900;
    }

    .menu-arrow {
        color: $gray-400;
        font-size: 0.9rem;
        transition: transform .12s;
    }

    &:hover {
        background: $gray-50;

        .menu-arrow { transform: translateX(2px); color: $gray-900; }
    }

    &:active { background: $gray-100; }
}

.menu-grid-empty {
    border: 1px solid $gray-200;
    padding: 20px;
    margin-bottom: 20px;
    color: $gray-500;
    font-size: 0.85rem;
    text-align: center;
}

/* ── 요약 카드 그리드 ── */
.summary-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 1px;
    background: $gray-200;
    border: 1px solid $gray-200;
}

.d-card {
    background: $white;
    padding: 20px;
    min-height: 168px;
    display: flex;
    flex-direction: column;
}

.d-card-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 14px;

    h3 {
        font-size: 0.82rem;
        font-weight: 700;
        color: $gray-500;
        letter-spacing: .03em;
        margin: 0;
        text-transform: uppercase;
    }
}

.d-link {
    border: 1px solid $gray-300;
    background: $white;
    color: $gray-700;
    font-size: 0.72rem;
    font-weight: 600;
    padding: 4px 10px;
    cursor: pointer;
    font-family: inherit;
    transition: background .12s, border-color .12s;

    &:hover { background: $gray-900; color: $white; border-color: $gray-900; }
}

.d-skel {
    height: 90px;
    background: $gray-100;
    animation: pulse 1.6s infinite ease-in-out;
}

.d-empty {
    color: $gray-400;
    font-size: 0.82rem;
    padding: 20px 0;
}

.d-body { display: flex; flex-direction: column; gap: 10px; }

.d-figure {
    display: flex;
    align-items: baseline;
    gap: 4px;
    margin-bottom: 2px;

    .d-num { font-size: 1.7rem; font-weight: 800; color: $black; font-variant-numeric: tabular-nums; }
    .d-unit { font-size: 0.8rem; color: $gray-500; font-weight: 600; }
}

.d-rows {
    margin: 0;
    display: flex;
    flex-direction: column;
}

.d-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 7px 0;
    border-top: 1px solid $gray-100;
    font-size: 0.82rem;

    &:first-child { border-top: none; }

    dt { color: $gray-500; margin: 0; }
    dd { margin: 0; color: $gray-900; font-weight: 700; font-variant-numeric: tabular-nums; }
}

.d-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;

    li {
        display: flex;
        justify-content: space-between;
        padding: 6px 0;
        border-top: 1px solid $gray-100;
        font-size: 0.82rem;

        &:first-child { border-top: none; }
    }

    .d-list-name { color: $gray-900; font-weight: 600; }
    .d-list-val  { color: $gray-700; font-variant-numeric: tabular-nums; }
}

.d-more { margin: 4px 0 0; font-size: 0.76rem; color: $gray-400; }

.d-status {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    font-size: 0.86rem;
    font-weight: 700;
    color: $gray-400;
    margin-bottom: 10px;

    .d-dot {
        width: 9px;
        height: 9px;
        background: $white;
        border: 1.5px solid $gray-400;
    }

    &.on {
        color: $gray-900;

        .d-dot { background: $gray-900; border-color: $gray-900; }
    }
}

.d-msg {
    margin: 10px 0 0;
    padding-top: 10px;
    border-top: 1px solid $gray-100;
    font-size: 0.76rem;
    color: $gray-500;
    line-height: 1.5;
}

@keyframes pulse {
    0%, 100% { opacity: .55; }
    50%      { opacity: .9; }
}

/* ── 반응형 ── */
@media (max-width: 768px) {
    .contents { padding: 16px 12px 80px; }
    .d-card { padding: 16px; min-height: unset; }
}

@media (max-width: 560px) {
    .summary-grid { grid-template-columns: 1fr; }
    .menu-grid { grid-template-columns: repeat(2, 1fr); }
}
</style>
