<template>
    <div id="auto-trade-mode">
        <BrandHeader :title="'운용모드'" back="/trade" />

        <div class="contents">
            <div v-if="isLoading" class="loader-rows">
                <div v-for="n in 4" :key="n" class="skeleton-row"></div>
            </div>

            <p v-else-if="loadError" class="empty">{{ loadError }}</p>

            <template v-else>
                <!-- ── 현재 상태 ── -->
                <section class="sec now" :class="{ halted: !state.trading }">
                    <div class="now-line">
                        <span class="dot"></span>
                        <strong>{{ state.trading ? '자동매매 중' : '매매 정지' }}</strong>
                    </div>
                    <p class="now-mode">{{ modeName(state.active_mode) }}</p>
                    <p class="now-sub">{{ state.active_from ? `${formatDateTime(state.active_from)}부터` : '적용 기록 없음' }}</p>
                    <p v-if="state.last_message" class="now-msg">{{ state.last_message }}</p>
                </section>

                <!-- ── 보유 포지션 ── -->
                <section class="sec">
                    <h3 class="sec-title">자동매매 보유 <span class="count">{{ positions.length }}</span></h3>
                    <ul v-if="positions.length" class="rows">
                        <li v-for="p in positions" :key="p.stock_code" class="pos">
                            <div class="pos-top">
                                <b>{{ p.stock_name }}</b>
                                <span class="code">{{ p.stock_code }}</span>
                                <span class="qty">{{ formatNumber(p.qty) }}주</span>
                            </div>
                            <dl class="pos-lines">
                                <div><dt>진입</dt><dd>{{ won(p.entry_price) }}</dd></div>
                                <div><dt>손절</dt><dd class="down">{{ won(p.stop_price) }}</dd></div>
                                <div><dt>익절</dt><dd class="up">{{ won(p.target_price) }}</dd></div>
                            </dl>
                        </li>
                    </ul>
                    <p v-else class="empty-row">보유 중인 종목이 없습니다.</p>
                </section>

                <!-- ── 모드 선택 ── -->
                <section class="sec">
                    <h3 class="sec-title">운용모드 선택</h3>
                    <button type="button" class="btn-apply" :class="{ danger: selectedIsHalt }"
                        :disabled="isBusy || !changed" @click="apply">
                        {{ applyLabel }}
                    </button>
                    <ul class="rows modes" role="radiogroup">
                        <li v-for="m in modes" :key="m.mode_code"
                            :class="['mode', { on: selected === m.mode_code, off: !m.selectable }]"
                            role="radio" :aria-checked="selected === m.mode_code" :aria-disabled="!m.selectable"
                            :tabindex="m.selectable ? 0 : -1"
                            @click="pick(m)" @keydown.enter.space.prevent="pick(m)">
                            <span class="radio"></span>
                            <div class="mode-body">
                                <div class="mode-head">
                                    <b>{{ m.mode_name }}</b>
                                    <span v-if="state.active_mode === m.mode_code" class="tag cur">현재</span>
                                    <span v-else-if="!m.selectable" class="tag">준비 중</span>
                                </div>
                                <p class="mode-desc" v-html="m.mode_desc"></p>
                            </div>
                        </li>
                    </ul>
                </section>

                <!-- ── 변경 이력 ── -->
                <section class="sec">
                    <h3 class="sec-title">변경 이력</h3>
                    <ul v-if="history.length" class="rows">
                        <li v-for="h in history" :key="h.log_id" class="log">
                            <span class="log-time">{{ formatDateTime(h.created_at) }}</span>
                            <span class="log-move">{{ modeName(h.from_mode) }} → <b>{{ modeName(h.to_mode) }}</b></span>
                            <span v-if="h.reason" class="log-reason">{{ h.reason }}</span>
                        </li>
                    </ul>
                    <p v-else class="empty-row">아직 변경 이력이 없습니다.</p>
                </section>

                <!-- ── 매도 수기 등록 ── -->
                <button type="button" class="link-row" @click="goManualSell">
                    <span>보유 종목에 지정 매도가 걸기</span>
                    <span aria-hidden="true">›</span>
                </button>
            </template>
        </div>

    </div>
</template>

<script setup>
import {
    fetchModes, fetchState, saveState, fetchHistory, formatNumber, formatDateTime,
} from '@scripts/useAutoTrade.js';

const router = useRouter();

const isLoading = ref(true);
const isBusy = ref(false);
const loadError = ref('');
const modes = ref([]);
const history = ref([]);
const state = reactive({ active_mode: null, active_from: null, trading: false, last_message: null, positions: [] });
const selected = ref('');

const errMsg = (e, fallback) => e?.response?.data?.error?.message || e?.response?.data?.message || fallback;

const load = async () => {
    try {
        const [modeList, st, hs] = await Promise.all([fetchModes(), fetchState(), fetchHistory(30)]);
        modes.value = modeList;
        Object.assign(state, st ?? {});
        history.value = hs;
        selected.value = state.active_mode ?? '';
        loadError.value = '';
    } catch (e) {
        loadError.value = errMsg(e, '운용모드 정보를 불러오지 못했습니다.');
    } finally {
        isLoading.value = false;
    }
};
onMounted(load);

const positions = computed(() => state.positions ?? []);
const modeName = (code) => code ? (modes.value.find(m => m.mode_code === code)?.mode_name ?? code) : '미설정';
const selectedMode = computed(() => modes.value.find(m => m.mode_code === selected.value) ?? null);
const selectedIsHalt = computed(() => !!selectedMode.value?.is_halt);
const changed = computed(() => !!selected.value && selected.value !== state.active_mode);
const applyLabel = computed(() => {
    if (!changed.value) return '현재 적용 중인 모드입니다';
    return selectedIsHalt.value ? '매매 정지하기' : `'${selectedMode.value?.mode_name}'로 전환`;
});

const won = (v) => (v === null || v === undefined) ? '-' : `${Math.round(Number(v)).toLocaleString()}원`;

const pick = (m) => { if (m.selectable) selected.value = m.mode_code; };

const apply = async () => {
    const name = selectedMode.value?.mode_name;
    const held = positions.value.length;
    const msg = selectedIsHalt.value
        ? `매매를 정지합니다.\n\n신규 매수뿐 아니라 손절·익절·지정가 매도도 모두 멈춥니다.`
          + (held ? `\n보유 중인 ${held}종목은 손절선에 닿아도 팔지 않습니다.` : '')
          + `\n\n계속할까요?`
        : `운용모드를 '${name}'로 바로 전환합니다.`
          + (held ? `\n보유 중인 ${held}종목은 새 모드의 매도 기준으로 관리됩니다.` : '')
          + `\n\n계속할까요?`;
    if (!confirm(msg)) return;

    isBusy.value = true;
    try {
        const res = await saveState(selected.value);
        if (res?.message) alert(res.message);
        await load();
    } catch (e) {
        alert(errMsg(e, '운용모드를 바꾸지 못했습니다.'));
    } finally {
        isBusy.value = false;
    }
};

const goManualSell = () => router.push({ path: '/auto-trade/limit-order' });
</script>

<style scoped lang="scss">
// 양봉상회 토큰(홈·배치관리와 동일)
$white:  #ffffff;
$line:   #EFE2BC;
$line-2: #EAD9A6;
$chip:   #F6EBC8;
$hero:   #74462A;
$brown:  #7A4423;
$ink:    #2B1D14;
$sub:    #6B5B4E;
$sub-2:  #7A6B5D;
$cream:  #FFF8E1;
$up:     #C8282A;
$down:   #1F5FBF;
$ok:     #2E9E5B;

#auto-trade-mode {
    min-height: 100vh;
    background: $white;
    color: $ink;
    text-align: left;
    font-family: 'Pretendard', 'IBM Plex Sans KR', -apple-system, 'Apple SD Gothic Neo', sans-serif;
    font-variant-numeric: tabular-nums;
}

.contents {
    max-width: 760px;
    margin: 0 auto;
    padding: 16px 16px calc(96px + env(safe-area-inset-bottom, 0px));
}

/* ── 섹션: 카드 없이 구분선 ── */
.sec { padding: 18px 0; border-bottom: 1px solid $line; }
.sec-title {
    margin: 0 0 6px;
    font-size: 17px;
    font-weight: 700;
    white-space: nowrap;
    .count { color: #A0662F; margin-left: 2px; }
}
.rows { margin: 0; padding: 0; list-style: none; }
.rows > li { border-bottom: 1px solid $line; &:last-child { border-bottom: 0; } }
.empty-row { margin: 6px 0 0; font-size: 14px; color: $sub-2; }
.empty { padding: 40px 0; text-align: center; color: $sub; }

/* ── 현재 상태 ── */
.now {
    padding-top: 8px;
    .now-line {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 15px;
        color: $ok;
        .dot { width: 8px; height: 8px; border-radius: 50%; background: currentColor; }
    }
    &.halted .now-line { color: $up; }
    .now-mode { margin: 6px 0 2px; font-size: 22px; font-weight: 800; }
    .now-sub { margin: 0; font-size: 13px; color: $sub-2; }
    .now-msg { margin: 10px 0 0; font-size: 13px; color: $sub; line-height: 1.5; }
}

/* ── 보유 포지션 ── */
.pos { padding: 12px 0; }
.pos-top {
    display: flex;
    align-items: baseline;
    gap: 6px;
    b { font-size: 16px; }
    .code { font-size: 12px; color: $sub-2; }
    .qty { margin-left: auto; font-size: 14px; color: $sub; }
}
.pos-lines {
    display: flex;
    gap: 16px;
    margin: 6px 0 0;
    font-size: 13px;
    div { display: flex; gap: 4px; }
    dt { color: $sub-2; }
    dd { margin: 0; font-weight: 600; }
    .up { color: $up; }
    .down { color: $down; }
}

/* ── 모드 목록 ── */
.mode {
    display: flex;
    gap: 12px;
    padding: 14px 0;
    cursor: pointer;
    outline: none;

    .radio {
        flex: none;
        width: 20px;
        height: 20px;
        margin-top: 1px;
        border: 2px solid $line-2;
        border-radius: 50%;
        box-sizing: border-box;
    }
    &.on .radio { border: 6px solid $hero; }
    &:focus-visible .mode-head b { text-decoration: underline; }
    &.off { cursor: default; .mode-body, .radio { opacity: .45; } }
}
.mode-body { min-width: 0; }
.mode-head {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 6px;
    b { font-size: 16px; }
}
.tag {
    padding: 2px 7px;
    border-radius: 6px;
    background: $chip;
    color: $sub;
    font-size: 11px;
    font-weight: 700;
    white-space: nowrap;
    &.cur { background: $hero; color: $cream; }
}
.mode-desc { margin: 4px 0 0; font-size: 13px; line-height: 1.55; color: $sub; :deep(b) { color: $ink; } }

/* ── 이력 ── */
.log {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr);
    align-items: baseline;
    gap: 2px 12px;
    padding: 10px 0;
    font-size: 14px;
    .log-time { grid-row: span 2; color: $sub-2; font-size: 12px; white-space: nowrap; }
    .log-reason { grid-column: 2; color: $sub; font-size: 12px; }
}

.link-row {
    display: flex;
    justify-content: space-between;
    width: 100%;
    padding: 16px 0;
    border: 0;
    border-bottom: 1px solid $line;
    background: none;
    color: $brown;
    font: inherit;
    font-size: 15px;
    font-weight: 600;
    cursor: pointer;
}

/* ── 적용 버튼: 모드 선택 제목 바로 아래 ── */
.btn-apply {
    display: block;
    width: 100%;
    min-height: 50px;
    margin: 8px 0 4px;
    border: 0;
    border-radius: 12px;
    background: $hero;
    color: $cream;
    font: inherit;
    font-size: 16px;
    font-weight: 700;
    cursor: pointer;
    &.danger { background: $up; color: $white; }
    &:disabled { background: $chip; color: $sub-2; cursor: default; }
    &:focus-visible { outline: 2px solid $brown; outline-offset: 2px; }
}

/* ── 스켈레톤 ── */
.loader-rows { padding-top: 8px; }
.skeleton-row {
    height: 64px;
    margin-bottom: 10px;
    border-radius: 8px;
    background: linear-gradient(90deg, #F6EFD9 25%, #FBF6E6 50%, #F6EFD9 75%);
    background-size: 200% 100%;
    animation: shimmer 1.2s infinite;
}
@keyframes shimmer { from { background-position: 200% 0; } to { background-position: -200% 0; } }
</style>
