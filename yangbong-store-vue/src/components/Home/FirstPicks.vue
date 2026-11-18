<template>
    <div id="first-picks">
        <header class="fp-top"><span class="brand"><img src="/favicon.svg" alt="" />양봉상회</span></header>

        <main class="fp-main">
            <section class="fp-head">
                <small>나는 {{ type.name }}</small>
                <h1>{{ title }}</h1>
                <p>궁금한 종목을 담으면 홈에서 바로 볼 수 있어요</p>
            </section>

            <section class="fp-list" aria-live="polite">
                <p v-if="isLoading" class="fp-msg">종목을 찾고 있어요</p>
                <p v-else-if="!rows.length" class="fp-msg">지금은 보여드릴 종목이 없어요. 홈에서 시장 흐름을 먼저 살펴보세요.</p>
                <article v-for="(r, i) in rows" v-else :key="r.code" class="fp-item">
                    <div class="line">
                        <span class="rank">{{ i + 1 }}</span>
                        <b class="name">{{ r.name }}</b>
                        <span class="px">{{ formatNumber(r.item.close) }}</span>
                        <span class="badge" :class="r.chg.cls">{{ r.pct }}</span>
                        <WatchStar :code="r.code" :name="r.name" :close="r.item.close" :rate="r.pct" @added="onAdded(r)" />
                    </div>
                    <p v-if="r.reason" class="why">✓ {{ r.reason }}</p>
                </article>
            </section>
        </main>

        <footer class="fp-foot">
            <p v-if="!isNative && watch.count" class="hint">담은 종목은 홈에서 볼 수 있어요. 앱 알림은 앱에서 받을 수 있어요.</p>
            <button type="button" class="cta" :class="{ off: needsPick }" :disabled="needsPick" @click="goHome">
                {{ needsPick ? '관심 종목을 하나 담아보세요' : '홈으로 가기' }}
            </button>
            <button v-if="needsPick" type="button" class="later" @click="goHome">나중에 할게요</button>
            <p class="notice">투자 판단과 책임은 본인에게 있으며, 원금 손실이 날 수 있습니다.</p>
        </footer>

        <div v-if="sheetFor" class="dim">
            <section class="sheet" role="dialog" aria-modal="true" aria-labelledby="fp-sheet-title">
                <i class="grab" aria-hidden="true"></i>
                <img src="/img/emoji/honey.png" alt="" />
                <h2 id="fp-sheet-title">{{ sheetFor.name }}에 변화가 있으면<br />알려드릴까요?</h2>
                <p>중요한 변화가 있을 때만 알려드려요.</p>
                <div class="sample"><b>양봉상회</b>{{ sheetFor.name }}, 오늘 거래량이 평소보다 크게 늘었어요</div>
                <button type="button" class="cta" :disabled="asking" @click="allow">알림 받기</button>
                <button type="button" class="later" @click="goHome">나중에</button>
            </section>
        </div>
    </div>
</template>

<script setup>
/** 첫 실행의 첫 가치: 내 성향에 맞는 종목 3개 → 관심 종목 담기 → 알림 제안. 가입 없이 진행한다. */
import { Capacitor } from '@capacitor/core';
import aibeesApi from '@scripts/aibeesApi.js';
import { evaluate } from '@scripts/indicators.js';
import { orderForType } from '@scripts/persona.js';
import { recoReasons } from '@scripts/recoReasons.js';
import { changeInfo, formatNumber } from '@scripts/stockSignals.js';
import { usePersonaStore } from '@scripts/stores/persona-store.js';
import { useWatchlistStore } from '@scripts/stores/watchlist-store.js';
import { enablePushNotifications } from '@scripts/usePushNotifications.js';

const router = useRouter();
const route = useRoute();
const persona = usePersonaStore();
const watch = useWatchlistStore();
const type = computed(() => persona.currentType);
// 개발 화면에서 앱의 알림 제안을 확인할 때만 ?native=1
const isNative = Capacitor.isNativePlatform() || (import.meta.env.DEV && route.query.native === '1');

const items = ref([]);
const isLoading = ref(true);
const sheetFor = ref(null);
const asking = ref(false);

const matched = computed(() => items.value.filter(item => evaluate(item, type.value.settings).match));
const rows = computed(() => orderForType(matched.value.length ? matched.value : items.value, type.value).slice(0, 3).map((item) => {
    const chg = changeInfo(item);
    return {
        item, chg,
        code: item.stock_code,
        name: item.stock_name,
        pct: chg.pct === null ? '–' : `${chg.pct > 0 ? '+' : (chg.pct < 0 ? '−' : '')}${Math.abs(chg.pct).toFixed(2)}%`,
        reason: recoReasons(item).top?.text ?? '',
    };
}));
const title = computed(() => (matched.value.length
    ? `오늘 내 조건에 맞는 종목 ${rows.value.length}개예요`
    : '오늘 살펴볼 종목이에요'));

const needsPick = computed(() => !isLoading.value && rows.value.length > 0 && !watch.count);
const goHome = () => router.replace('/home');
const onAdded = (r) => { if (isNative && !watch.alerts && !sheetFor.value) sheetFor.value = r; };
const allow = async () => {
    asking.value = true;
    watch.setAlerts(await enablePushNotifications());
    goHome();
};

onMounted(async () => {
    try {
        const { data } = await aibeesApi.get('/api/v1/stocks/buy-target');
        items.value = Array.isArray(data?.data) ? data.data : [];
    } catch (e) {
        console.error('[first-picks] 종목 조회 실패', e);
    } finally {
        isLoading.value = false;
    }
});
</script>

<style scoped lang="scss">
@use '@@/_home-tokens.scss' as *;

$btn: #5A3C08;
#first-picks { min-height: 100vh; min-height: 100dvh; display: flex; flex-direction: column; background: $card; color: $ink; text-align: left; font-family: $font-body; font-variant-numeric: tabular-nums; letter-spacing: -0.2px; -webkit-font-smoothing: antialiased; }
button { border: 0; font: inherit; letter-spacing: inherit; cursor: pointer; }
.fp-top { height: 56px; padding: 0 $pad-x; display: flex; align-items: center; flex: none; }
.brand { display: inline-flex; align-items: center; gap: 7px; font-size: 16px; font-weight: 700; img { width: 24px; height: 24px; } }
.fp-main { flex: 1; width: 100%; box-sizing: border-box; padding: 6px $pad-x 16px; }
.fp-head { small { font-size: 13px; font-weight: 700; color: $amber-700; } h1 { margin: 6px 0 0; font-size: 24px; line-height: 1.32; letter-spacing: -0.6px; word-break: keep-all; } p { margin: 6px 0 0; font-size: 14px; color: $sub; } }
.fp-list { margin-top: 12px; }
.fp-msg { padding: 44px 0; text-align: center; font-size: 14px; color: $sub; word-break: keep-all; }
.fp-item { padding: 13px 0 15px; border-bottom: 1px solid $line; &:last-child { border-bottom: 0; } }
.line { display: flex; align-items: center; gap: 8px; }
.rank { width: 15px; flex: none; color: $amber-700; font-weight: 700; }
.name { flex: 1; min-width: 0; font-size: 16px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.px { flex: none; font-weight: 600; }
.badge { flex: none; min-width: 58px; height: 24px; border-radius: $radius-sm; font-size: 12px; font-weight: 700; color: $sub; background: $band; display: inline-flex; align-items: center; justify-content: center; &.up { color: $up; background: $up-bg; } &.down { color: $down; background: $down-bg; } }
.why { margin: 8px 0 0 23px; padding: 9px 10px; border-radius: 9px; background: $honey-strip; color: $honey-ink; font-size: 13px; }
.fp-foot { flex: none; padding: 8px $pad-x calc(18px + env(safe-area-inset-bottom, 0px)); }
.hint { margin: 0 0 10px; padding: 10px 12px; border-radius: 10px; background: $band; color: $sub-ink; font-size: 13px; text-align: center; word-break: keep-all; }
.cta { width: 100%; height: 54px; border-radius: $radius; background: $btn; color: #fff; font-size: 17px; font-weight: 700; &:disabled { opacity: .6; cursor: default; } &.off { background: $band; color: $sub; opacity: 1; } }
.later { width: 100%; height: 40px; margin-top: 4px; background: transparent; color: $sub; font-size: 14px; }
.notice { margin: 8px 0 0; text-align: center; font-size: 11.5px; line-height: 1.5; color: $sub; word-break: keep-all; }
.dim { position: fixed; inset: 0; z-index: 1200; display: flex; align-items: flex-end; justify-content: center; background: rgba(25, 31, 40, .42); }
.sheet { width: 100%; max-width: 480px; box-sizing: border-box; padding: 12px 22px calc(18px + env(safe-area-inset-bottom, 0px)); border-radius: 16px 16px 0 0; background: $card;
    .grab { display: block; width: 36px; height: 4px; margin: 0 auto 18px; border-radius: 2px; background: $line; }
    img { display: block; width: 44px; height: 44px; }
    h2 { margin: 12px 0 0; font-size: 21px; line-height: 1.35; letter-spacing: -0.5px; word-break: keep-all; }
    p { margin: 6px 0 0; font-size: 14px; line-height: 1.5; color: $sub-ink; }
    .sample { margin: 14px 0 16px; padding: 12px; border-radius: $radius; background: $honey-strip; color: $honey-ink; font-size: 13px; line-height: 1.45; b { display: block; margin-bottom: 2px; } }
}
@media (min-width: 700px) {
    .fp-top { padding: 0 36px; height: 68px; }
    .fp-main { display: grid; grid-template-columns: 250px minmax(0, 1fr); gap: 34px; align-items: start; padding: 20px 36px; }
    .fp-head h1 { font-size: 30px; }
    .fp-list { margin-top: 0; }
    .fp-foot { width: 100%; max-width: 420px; margin-left: auto; padding-right: 36px; box-sizing: border-box; }
    .dim { align-items: center; }
    .sheet { border-radius: 16px; padding-bottom: 18px; }
}
@media (min-width: 1024px) {
    #first-picks { padding: 0 max(44px, calc((100vw - 1120px) / 2)); }
    .fp-top, .fp-main, .fp-foot { padding-left: 0; padding-right: 0; }
    .fp-main { display: block; flex: none; }
    .fp-head h1 { font-size: 34px; }
    .fp-list { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; margin-top: 24px; }
    .fp-msg { grid-column: 1 / -1; }
    .fp-item { padding: 16px; border: 1px solid $line; border-radius: $radius; &:last-child { border-bottom: 1px solid $line; } }
    .line { flex-wrap: wrap; .name { flex: 1 1 calc(100% - 70px); } .px { flex: 1; margin-left: 23px; } }
    .why { margin-left: 0; margin-top: 12px; }
    .fp-foot { max-width: 360px; margin: 8px 0 28px; }
}
</style>
