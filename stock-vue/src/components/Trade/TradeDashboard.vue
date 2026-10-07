<template>
    <div id="trade-dashboard">

        <!-- ════════ 헤더(v2): 트레이드 + 갱신 시각 + 새로고침. 모바일에서는 sticky(+세이프 에어리어) ════════ -->
        <header class="dash-header" data-ad-anchor>
            <div class="dh-row">
                <h1>트레이드</h1>
                <div class="dh-right">
                    <span v-if="updatedAt" class="dh-time">{{ updatedAt }} 갱신</span>
                    <button type="button" class="icon-btn" aria-label="새로고침" @click="reloadAll">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 11a8 8 0 0 0-14.3-4.9L4 8"></path><path d="M4 4v4h4"></path><path d="M4 13a8 8 0 0 0 14.3 4.9L20 16"></path><path d="M20 20v-4h-4"></path></svg>
                    </button>
                </div>
            </div>
        </header>

        <main class="dash-main">

            <!-- ── 자산현황 히어로: 총자산 + 예수금/주문가능/평가액 ── -->
            <section class="asset-hero" :class="{ skeleton: loadingAccount }" aria-label="자산현황">
                <div class="ah-top">
                    <span class="ah-label">총자산</span>
                    <button v-if="assetLink" type="button" class="ah-link" @click="goPath(assetLink)">내 자산 ›</button>
                </div>
                <template v-if="!loadingAccount">
                    <template v-if="account">
                        <span class="ah-amount">{{ fmtWon(account.total_asset) }}<span class="won">원</span></span>
                        <!-- deposit=예수금(ord_psbl_cash) / user_balance=주문가능금액(nrcvb_buy_amt).
                             증거금징수율·미체결 주문 때문에 서로 다른 값이다. -->
                        <dl class="ah-stats">
                            <div><dt>예수금</dt><dd>{{ fmtWon(account.deposit) }}원</dd></div>
                            <div><dt>주문가능</dt><dd>{{ fmtWon(account.user_balance) }}원</dd></div>
                            <div><dt>주식평가</dt><dd>{{ fmtWon(account.stock_amount) }}원</dd></div>
                        </dl>
                    </template>
                    <p v-else class="ah-empty">데이터를 불러올 수 없습니다.</p>
                </template>
            </section>

            <!-- ── 하위 메뉴 바로가기 ── -->
            <section v-if="tradeChildren.length" class="quick-grid" aria-label="바로가기">
                <button v-for="c in tradeChildren" :key="c.menu_code" type="button" class="quick-tile"
                    @click="goPath(childPath(c))">
                    <span class="qt-label">{{ c.menu_title || c.menu_name }}</span>
                    <span class="qt-arrow" aria-hidden="true">›</span>
                </button>
            </section>
            <p v-else class="quick-empty">등록된 하위 메뉴가 없습니다.</p>

            <div class="card-grid">

                <!-- 자동매매(Worker) 상태 -->
                <article class="d-card">
                    <header class="d-card-head">
                        <h3>자동매매 상태</h3>
                        <button v-if="workerLink" type="button" class="d-link" @click="goPath(workerLink)">자세히 ›</button>
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

                <!-- 보유종목 -->
                <article class="d-card">
                    <header class="d-card-head">
                        <h3>보유 종목</h3>
                        <button v-if="assetLink" type="button" class="d-link" @click="goPath(assetLink)">자세히 ›</button>
                    </header>

                    <div v-if="loadingPortfolio" class="d-skel"></div>
                    <div v-else-if="!holdings.length" class="d-empty">보유 종목이 없어요.</div>
                    <div v-else class="d-body">
                        <div class="d-figure">
                            <span class="d-num">{{ holdings.length }}</span>
                            <span class="d-unit">종목</span>
                        </div>
                        <ul class="d-list">
                            <li v-for="h in holdings.slice(0, 3)" :key="h.stock_code">
                                <span class="d-list-name">{{ h.stock_name }}</span>
                                <span class="d-list-val" :class="pnlClass(h.profit)">{{ pnlMark(h.profit) }}{{ fmtSigned(h.profit) }}</span>
                            </li>
                        </ul>
                        <p v-if="holdings.length > 3" class="d-more">외 {{ holdings.length - 3 }}종목</p>
                    </div>
                </article>

                <!-- 매수 / 매도 정책 요약 -->
                <article class="d-card wide">
                    <header class="d-card-head">
                        <h3>매수 · 매도 정책</h3>
                        <button v-if="buyLink" type="button" class="d-link" @click="goPath(buyLink)">자세히 ›</button>
                    </header>

                    <div v-if="loadingOptions" class="d-skel"></div>
                    <div v-else-if="!options" class="d-empty">데이터를 불러올 수 없습니다.</div>
                    <dl v-else class="d-rows two-col">
                        <div class="d-row"><dt>손절</dt><dd>-{{ pct(options.s1_stop_loss_pct, 0.05) }}%</dd></div>
                        <div class="d-row"><dt>익절</dt><dd>+{{ pct(options.s1_take_profit_pct, 0.30) }}%</dd></div>
                        <div class="d-row"><dt>트레일링</dt><dd>{{ bool(options.s1_use_trailing, 1) ? '사용' : '미사용' }}</dd></div>
                        <div class="d-row"><dt>보유 한도</dt><dd>{{ options.s1_max_hold_bars ?? 12 }}봉</dd></div>
                        <div class="d-row"><dt>RSI 신뢰구간</dt><dd>{{ options.s1_rsi_ideal_low ?? 40 }} ~ {{ options.s1_rsi_ideal_high ?? 65 }}</dd></div>
                        <div class="d-row"><dt>진입 필터</dt><dd>{{ enabledFilterCount }} / {{ FILTER_KEYS.length }} 사용</dd></div>
                    </dl>
                </article>

            </div>
        </main>
    </div>
</template>

<script setup>
import aibeesApi from '@scripts/aibeesApi.js';
import { assUserSession } from '@scripts/stores/user-stores';
import { fetchModes, fetchState, RUN_STATE_LABEL } from '@scripts/useAutoTrade.js';

const router = useRouter();
const userSession = assUserSession();

const userId = computed(() => userSession.user?.loginInfo?.user_id);

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

// 국내 관례: 이익=적색, 손실=청색. 색만으로 구분하지 않도록 ▲/▼ 도 붙인다.
const pnlClass = (v) => {
    const n = toNum(v);
    if (n === null || n === 0) return '';
    return n > 0 ? 'up' : 'down';
};
const pnlMark = (v) => {
    const n = toNum(v);
    if (n === null || n === 0) return '';
    return n > 0 ? '▲ ' : '▼ ';
};

/* ── 갱신 ── */
const updatedAt = ref('');
const stampUpdated = () => {
    const d = new Date();
    updatedAt.value = `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
};

const reloadAll = () => {
    stampUpdated();
    loadingAccount.value = loadingPortfolio.value = loadingOptions.value = loadingWorker.value = true;
    fetchAccount();
    fetchPortfolio();
    fetchOptions();
    fetchWorker();
};

onMounted(() => {
    allMenu.value = userSession.loadMenuList() ?? [];
    stampUpdated();
    fetchAccount();
    fetchPortfolio();
    fetchOptions();
    fetchWorker();
});
</script>

<style scoped lang="scss">
/* ════════════════════════════════════════════════════════════════
 * 양봉상회 트레이드 대시보드 (홈·내 자산과 같은 토큰)
 *   헤더/탭바 #FFF6D2 · 카드 #FFF · 테두리 #EFE2BC · 갈색 #74462A · 노랑 #F6C445
 *   상승 #C8282A / 하락 #1F5BD1
 * ════════════════════════════════════════════════════════════════ */
$bg:      #FFFBEA;
$bar:     #FFF6D2;
$line:    #EFE2BC;
$hero:    #74462A;
$brown:   #7A4423;
$ink:     #2B1D14;
$sub:     #6B5B4E;
$sub-2:   #7A6B5D;
$yellow:  #F6C445;
$up:      #C8282A;
$down:    #1F5BD1;

#trade-dashboard {
    min-height: 100vh;
    background: $bg;
    color: $ink;
    text-align: left;
    font-family: 'Pretendard', -apple-system, sans-serif;
    font-variant-numeric: tabular-nums;
}

/* ── 헤더 ── */
.dash-header {
    position: sticky;
    top: env(safe-area-inset-top, 0px);   // 상태바 영역은 App.vue 의 고정 덮개가 가린다
    z-index: 50;
    background: $bar;
    border-bottom: 1px solid $line;
    padding: 0 8px 0 16px;

    .dh-row { display: flex; align-items: center; justify-content: space-between; min-height: 52px; }
    h1 { margin: 0; font-size: 20px; font-weight: 700; color: #3A200F; }
    .dh-right { display: flex; align-items: center; gap: 2px; }
    .dh-time { font-size: 12px; color: $sub-2; }
    .icon-btn {
        width: 44px; height: 44px; border: 0; background: transparent; color: #5C3118;
        display: inline-flex; align-items: center; justify-content: center; cursor: pointer;
    }
}

.dash-main {
    max-width: 960px;
    margin: 0 auto;
    padding: 16px 16px 24px;
    display: flex;
    flex-direction: column;
    gap: 14px;
}

/* ── 자산현황 히어로 ── */
.asset-hero {
    background: $hero;
    border-radius: 20px;
    padding: 18px;
    color: #FFF8E1;
    display: flex;
    flex-direction: column;
    gap: 6px;
    box-sizing: border-box;
    min-height: 128px;

    &.skeleton { animation: pulse 1.6s infinite ease-in-out; }

    .ah-top { display: flex; align-items: center; justify-content: space-between; }
    .ah-label { font-size: 13px; color: #E8D5B8; }
    .ah-link {
        border: 0; background: transparent; color: #F3DCA8; font-size: 13px;
        min-height: 36px; padding: 0 2px; cursor: pointer; font-family: inherit;
    }
    .ah-amount {
        font-size: 32px; font-weight: 700; letter-spacing: -.5px;
        .won { font-size: 18px; font-weight: 500; margin-left: 2px; }
    }
    .ah-empty { margin: 0; font-size: 14px; color: #F5E6CC; }

    .ah-stats {
        margin: 8px 0 0;
        padding-top: 12px;
        border-top: 1px solid rgba(255, 248, 225, .18);
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 8px;

        dt { font-size: 12px; color: #E8D5B8; margin: 0 0 2px; }
        dd { margin: 0; font-size: 14px; font-weight: 700; color: #FFF8E1; word-break: keep-all; }
    }
}

/* ── 하위 메뉴 바로가기 ── */
.quick-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 10px;
}
.quick-tile {
    min-height: 52px;
    padding: 0 14px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    background: #fff;
    border: 1px solid $line;
    border-radius: 14px;
    cursor: pointer;
    font-family: inherit;
    color: $ink;
    text-align: left;

    .qt-label { font-size: 14px; font-weight: 600; }
    .qt-arrow { font-size: 18px; color: #A0662F; }
    &:active { background: #FFFDF5; }
}
.quick-empty { margin: 0; padding: 14px; text-align: center; font-size: 13px; color: $sub; background: #fff; border: 1px solid $line; border-radius: 14px; }

/* ── 요약 카드 ── */
.card-grid {
    display: grid;
    grid-template-columns: 1fr;
    gap: 14px;
}

.d-card {
    background: #fff;
    border: 1px solid $line;
    border-radius: 16px;
    padding: 16px;
    display: flex;
    flex-direction: column;
}

.d-card-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 10px;

    h3 { font-size: 15px; font-weight: 700; margin: 0; color: $ink; }
}

.d-link {
    border: 0;
    background: transparent;
    color: $brown;
    font-size: 13px;
    font-weight: 600;
    min-height: 36px;
    padding: 0 2px;
    cursor: pointer;
    font-family: inherit;
}

.d-skel { height: 90px; border-radius: 12px; background: #F6EFD6; animation: pulse 1.6s infinite ease-in-out; }
.d-empty { color: $sub; font-size: 13px; padding: 16px 0; }

.d-body { display: flex; flex-direction: column; gap: 10px; }

.d-figure {
    display: flex;
    align-items: baseline;
    gap: 4px;
    .d-num { font-size: 26px; font-weight: 700; }
    .d-unit { font-size: 13px; color: $sub; font-weight: 600; }
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
    min-height: 40px;
    border-top: 1px solid #F3EAD2;
    font-size: 14px;

    &:first-child { border-top: none; }
    dt { color: $sub; margin: 0; }
    dd { margin: 0; font-weight: 700; }
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
        align-items: center;
        min-height: 40px;
        border-top: 1px solid #F3EAD2;
        font-size: 14px;
        &:first-child { border-top: none; }
    }
    .d-list-name { font-weight: 600; }
    .d-list-val { font-weight: 700; &.up { color: $up; } &.down { color: $down; } }
}
.d-more { margin: 2px 0 0; font-size: 12px; color: $sub-2; }

// 운용 상태: 점 + 글자(색만으로 구분하지 않는다)
.d-status {
    align-self: flex-start;
    display: inline-flex;
    align-items: center;
    gap: 7px;
    padding: 5px 12px;
    border-radius: 999px;
    background: #F1ECE2;
    color: $sub;
    font-size: 13px;
    font-weight: 700;

    .d-dot { width: 8px; height: 8px; border-radius: 4px; background: #9A8F84; }
    &.on { background: $bar; color: #5C3118; border: 1px solid #EAD9A6; padding: 4px 11px;
        .d-dot { background: #2E9E5B; } }
}

.d-msg {
    margin: 4px 0 0;
    padding-top: 10px;
    border-top: 1px solid #F3EAD2;
    font-size: 12px;
    color: $sub;
    line-height: 1.5;
}

@keyframes pulse {
    0%, 100% { opacity: .55; }
    50%      { opacity: .9; }
}

/* ── 반응형 ── */
@media (min-width: 768px) {
    .card-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .d-card.wide { grid-column: 1 / -1; }
    .d-rows.two-col { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); column-gap: 24px; }
    .d-rows.two-col .d-row:nth-child(2) { border-top: none; }
    .quick-grid { grid-template-columns: repeat(4, minmax(0, 1fr)); }
}

// 데스크톱: 상단 내비(Lnb)가 있으니 헤더는 흐름에 둔다
@media (min-width: 640px) {
    .dash-header { position: static; }
    .dash-main { padding-top: 20px; }
}
</style>
