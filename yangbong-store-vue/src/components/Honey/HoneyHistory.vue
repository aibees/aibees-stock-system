<template>
    <div id="honey-history">
        <BrandHeader title="내 꿀" :back="HONEY_PATH" />
        <main class="hh">
            <section class="sum">
                <p class="bal">{{ fmt(honey.balance) }}<span>꿀</span></p>
                <p class="exp">{{ s?.expiringSoon ? `30일 안에 사라질 꿀 ${fmt(s.expiringSoon)} · ` : '' }}모은 날로부터 1년 뒤 사라져요</p>
                <p v-if="passText" class="pass">{{ passText }}</p>
            </section>
            <div class="seg" role="tablist" aria-label="내역 구분">
                <button v-for="t in TABS" :key="t.key" type="button" role="tab" :aria-selected="tab === t.key ? 'true' : 'false'"
                    :class="{ on: tab === t.key }" @click="tab = t.key">{{ t.label }}</button>
            </div>
            <p v-if="loading && !rows.length" class="msg">불러오고 있어요</p>
            <p v-else-if="!shown.length" class="msg">아직 내역이 없어요</p>
            <template v-for="g in groups" :key="g.day">
                <p class="day">{{ g.day }}</p>
                <div v-for="r in g.items" :key="r.id" class="row">
                    <div><b>{{ label(r) }}</b><small>{{ timeText(r.at) }}</small></div>
                    <span class="v" :class="{ m: r.amount < 0 }">{{ r.amount > 0 ? '+' : '−' }}{{ fmt(Math.abs(r.amount)) }}</span>
                </div>
            </template>
            <button v-if="more" type="button" class="more" :disabled="loading" @click="loadMore">더 보기</button>
        </main>
    </div>
</template>

<script setup>
/** 꿀 내역 — 모은 꿀·쓴 꿀을 날짜별로. */
import { HONEY_KIND_LABEL, useHoneyStore } from '@scripts/stores/honey-store.js';
import { HONEY_PATH } from '@scripts/support.js';

const honey = useHoneyStore();
const s = computed(() => honey.summary);
const TABS = [{ key: 'all', label: '전체' }, { key: 'in', label: '모음' }, { key: 'out', label: '씀' }];
const tab = ref('all');
const rows = ref([]);
const loading = ref(false);
const more = ref(false);
const fmt = (n) => Number(n ?? 0).toLocaleString();

const label = (r) => HONEY_KIND_LABEL[r.kind] ?? '꿀';
const shown = computed(() => rows.value.filter(r => tab.value === 'all' || (tab.value === 'in' ? r.amount > 0 : r.amount < 0)));
const dayText = (ms) => {
    const d = new Date(ms);
    const t = new Date();
    if (d.toDateString() === t.toDateString()) return '오늘';
    return `${d.getMonth() + 1}월 ${d.getDate()}일`;
};
const timeText = (ms) => new Date(ms).toLocaleTimeString('ko-KR', { hour: 'numeric', minute: '2-digit' });
const groups = computed(() => {
    const out = [];
    for (const r of shown.value) {
        const day = dayText(r.at);
        if (!out.length || out.at(-1).day !== day) out.push({ day, items: [] });
        out.at(-1).items.push(r);
    }
    return out;
});
const passText = computed(() => {
    const until = honey.dayPassUntil;
    if (!until || until < Date.now()) return '';
    const d = new Date(until);
    return `프리미엄 하루 이용권 사용 중 · ${d.getMonth() + 1}/${d.getDate()} ${timeText(until)}까지`;
});

const loadMore = async () => {
    loading.value = true;
    try {
        const before = rows.value.at(-1)?.id;
        const next = await honey.ledger(before);
        rows.value = [...rows.value, ...next];
        more.value = next.length >= 50;
    } catch { more.value = false; } finally { loading.value = false; }
};
onMounted(() => { honey.load(); loadMore(); });
</script>

<style scoped lang="scss">
@use '@@/_home-tokens.scss' as *;

#honey-history { min-height: 100vh; background: $card; color: $ink; text-align: left; font-family: $font-body; letter-spacing: -0.2px; }
button { font: inherit; letter-spacing: inherit; cursor: pointer; border: 0; }
.hh { max-width: 560px; margin: 0 auto; padding: 4px $pad-x 40px; box-sizing: border-box; }
.sum { padding: 18px; border-radius: 14px; background: $honey-strip;
    .bal { margin: 0; font-size: 28px; font-weight: 800; color: $honey-ink; letter-spacing: -.7px; span { font-size: 16px; margin-left: 2px; } }
    .exp { margin: 6px 0 0; font-size: 13px; color: #7A5A1E; } .pass { margin: 8px 0 0; font-size: 13px; font-weight: 700; color: $amber-700; } }
.seg { display: flex; gap: 6px; margin: 16px 0 4px; button { padding: 7px 13px; border-radius: 17px; background: $band; font-size: 13.5px; font-weight: 600; color: $sub-ink; &.on { background: $ink; color: #fff; } } }
.msg { padding: 32px 0; text-align: center; font-size: 14px; color: $sub; }
.day { margin: 16px 0 2px; font-size: 12.5px; color: $sub; font-weight: 700; }
.row { display: flex; justify-content: space-between; align-items: center; padding: 12px 0; border-bottom: 1px solid $line;
    b { display: block; font-size: 15px; } small { font-size: 12.5px; color: $sub; }
    .v { font-weight: 800; font-size: 15.5px; color: $amber-700; &.m { color: $sub-ink; } } }
.more { width: 100%; height: 44px; margin-top: 14px; border-radius: $radius; background: $band; color: $sub-ink; font-size: 14px; font-weight: 600; }
</style>
