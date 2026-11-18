<template>
    <section class="gl" aria-label="주식 용어 사전">
        <label class="gl-search">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><circle cx="11" cy="11" r="7"></circle><path d="m20 20-3.5-3.5"></path></svg>
            <span class="sr-only">용어 검색</span>
            <input v-model="query" type="search" placeholder="용어를 검색해 보세요" autocomplete="off" />
            <button v-if="query" type="button" class="gl-clear" aria-label="검색어 지우기" @click="query = ''">×</button>
        </label>

        <div class="gl-chips" role="group" aria-label="용어 분류">
            <button v-for="c in chips" :key="c" type="button" :class="{ on: c === category }"
                :aria-pressed="c === category ? 'true' : 'false'" @click="category = c">{{ c }}</button>
        </div>

        <p class="gl-count">{{ countText }}</p>

        <p v-if="!groups.length" class="gl-empty">찾는 용어가 없어요. 다른 말로 검색해 보세요.</p>

        <div v-for="g in groups" :key="g.name">
            <h2 class="gl-group">{{ g.name }}</h2>
            <article v-for="t in g.items" :id="`term-${t.id}`" :key="t.id" class="gl-term" :class="{ open: openId === t.id }">
                <button type="button" class="gl-row" :aria-expanded="openId === t.id ? 'true' : 'false'"
                    :aria-controls="`term-body-${t.id}`" @click="toggle(t.id)">
                    <span class="gl-text"><b>{{ t.term }}</b><small>{{ t.short }}</small></span>
                    <svg class="gl-chev" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m6 9 6 6 6-6"></path></svg>
                </button>

                <div v-if="openId === t.id" :id="`term-body-${t.id}`" class="gl-body">
                    <h3>쉽게 말하면</h3>
                    <p>{{ t.easy }}</p>
                    <h3>예시</h3>
                    <p class="gl-example">{{ t.example }}</p>

                    <div v-if="t.caution" class="gl-caution">
                        <b>헷갈리기 쉬워요</b>
                        <p>{{ t.caution }}</p>
                        <!-- 양봉·음봉: 시가와 전날 종가의 차이를 그림으로 -->
                        <div v-if="t.figure" class="gl-fig">
                            <svg viewBox="0 0 112 88" role="img" :aria-label="`${t.figure.prev}, 오늘 캔들`">
                                <template v-if="t.figure.kind === 'bull'">
                                    <line class="prev" x1="4" y1="14" x2="108" y2="14"></line>
                                    <text x="4" y="10">{{ t.figure.prev }}</text>
                                    <line class="wick up" x1="56" y1="34" x2="56" y2="82"></line>
                                    <rect class="body up" x="45" y="42" width="22" height="30" rx="2"></rect>
                                </template>
                                <template v-else>
                                    <line class="prev" x1="4" y1="74" x2="108" y2="74"></line>
                                    <text x="4" y="86">{{ t.figure.prev }}</text>
                                    <line class="wick down" x1="56" y1="6" x2="56" y2="56"></line>
                                    <rect class="body down" x="45" y="14" width="22" height="32" rx="2"></rect>
                                </template>
                            </svg>
                            <span>오늘은 전날보다 <b :class="t.figure.kind === 'bull' ? 'down' : 'up'">{{ t.figure.change }}</b>{{ t.figure.text }}</span>
                        </div>
                    </div>

                    <template v-if="relatedOf(t).length">
                        <h3>관련 용어</h3>
                        <div class="gl-related">
                            <button v-for="r in relatedOf(t)" :key="r.id" type="button" @click="openRelated(r)">{{ r.term }}</button>
                        </div>
                    </template>

                    <button v-if="lessonOf(t)" type="button" class="gl-lesson" @click="router.push(stagePath(lessonOf(t)))">
                        {{ lessonOf(t).short || lessonOf(t).title }} 강의 보기 <i aria-hidden="true">›</i>
                    </button>
                </div>
            </article>
        </div>
    </section>
</template>

<script setup>
/** 트레이닝 > 용어 사전 탭: 검색 · 분류 · 가나다 목록. 항목은 한 번에 하나만 펼친다. */
import { allStages, stagePath } from '@scripts/training.js';
import { glossaryCategories, glossaryTerms, groupOf, matchesTerm } from '@scripts/glossary.js';

const ALL = '전체';
const router = useRouter();
const terms = glossaryTerms();
const chips = [ALL, ...glossaryCategories()];

const query = ref('');
const category = ref(ALL);
const openId = ref(null);

const filtered = computed(() => terms.filter(t =>
    (category.value === ALL || t.category === category.value) && matchesTerm(t, query.value)));

const groups = computed(() => {
    const out = [];
    filtered.value.forEach((t) => {
        const name = groupOf(t.term);
        if (out.at(-1)?.name !== name) out.push({ name, items: [] });
        out.at(-1).items.push(t);
    });
    return out;
});

const countText = computed(() => (query.value.trim()
    ? `검색 결과 ${filtered.value.length}개`
    : `${category.value} ${filtered.value.length}개 · 가나다순`));

// 검색 결과가 하나면 바로 펼친다
watch(filtered, (list) => {
    if (query.value.trim() && list.length === 1) openId.value = list[0].id;
});

const toggle = (id) => { openId.value = openId.value === id ? null : id; };
const relatedOf = (t) => (t.related ?? []).map(name => terms.find(x => x.term === name)).filter(Boolean);
const lessonOf = (t) => (t.lesson ? allStages().find(s => s.key === t.lesson) ?? null : null);

const openRelated = async (t) => {
    query.value = '';
    category.value = ALL;
    openId.value = t.id;
    await nextTick();
    document.getElementById(`term-${t.id}`)?.scrollIntoView({ block: 'start' });
};
</script>

<style scoped lang="scss">
@use '@@/_home-tokens.scss' as *;

button { font: inherit; letter-spacing: inherit; }
.sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
.gl { background: $card; padding-bottom: 12px; }

.gl-search {
    display: flex;
    align-items: center;
    gap: 8px;
    height: 44px;
    margin: 14px $pad-x 0;
    padding: 0 6px 0 14px;
    border-radius: $radius;
    background: $band;
    color: $sub;
    > svg { flex: none; width: 17px; height: 17px; }
    input {
        flex: 1;
        min-width: 0;
        border: 0;
        outline: 0;
        background: transparent;
        color: $ink;
        font-size: 15px;
        -webkit-appearance: none;
        appearance: none;
        &::placeholder { color: $sub; }
        &::-webkit-search-cancel-button { -webkit-appearance: none; }
    }
    &:focus-within { box-shadow: 0 0 0 2px $honey-300; }
}
.gl-clear { width: 32px; height: 32px; border: 0; background: transparent; color: $sub; font-size: 19px; cursor: pointer; }

.gl-chips {
    display: flex;
    gap: 4px;
    padding: 12px $pad-x;
    overflow-x: auto;
    scrollbar-width: none;
    &::-webkit-scrollbar { display: none; }
    button {
        flex: none;
        height: 34px;
        padding: 0 12px;
        border: 0;
        border-radius: 8px;
        background: transparent;
        color: $sub;
        font-size: 14px;
        cursor: pointer;
        &.on { background: $honey-300; color: $honey-ink; font-weight: 700; }
    }
}
.gl-count { margin: 0; padding: 2px $pad-x 4px; font-size: 13px; color: $sub; }
.gl-empty { margin: 0; padding: 48px $pad-x; text-align: center; font-size: 14px; color: $sub; }
.gl-group { margin: 0; padding: 18px $pad-x 2px; font-size: 13px; font-weight: 700; color: $amber-700; }

.gl-term { margin: 0 $pad-x; border-bottom: 1px solid $line; scroll-margin-top: 104px; &:last-child { border-bottom: 0; } }
.gl-row {
    width: 100%;
    min-height: 62px;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 0;
    border: 0;
    background: transparent;
    color: $ink;
    text-align: left;
    cursor: pointer;
    -webkit-tap-highlight-color: transparent;
}
.gl-text {
    flex: 1;
    min-width: 0;
    b { display: block; font-size: 16px; font-weight: 600; }
    small { display: block; margin-top: 3px; font-size: 13px; line-height: 1.4; color: $sub; word-break: keep-all; }
}
.open .gl-text small { color: $sub-ink; }
.gl-chev { flex: none; width: 15px; height: 15px; color: $sub-2; transition: transform .15s ease; }
.open .gl-chev { transform: rotate(180deg); }

.gl-body {
    padding-bottom: 18px;
    h3 { margin: 14px 0 5px; font-size: 12px; font-weight: 600; color: $sub; &:first-child { margin-top: 0; } }
    p { margin: 0; font-size: 14.5px; line-height: 1.6; color: $sub-ink; word-break: keep-all; }
}
.gl-body .gl-example { padding: 11px 12px; border-radius: 10px; background: $band; color: $ink; font-size: 14px; }
.gl-caution {
    margin-top: 14px;
    padding: 13px 14px;
    border-radius: $radius;
    background: $honey-strip;
    > b { display: block; margin-bottom: 4px; font-size: 13px; color: $amber-700; }
    p { color: $honey-ink; font-size: 14px; }
}
.gl-fig {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-top: 10px;
    svg { flex: none; width: 112px; height: 88px; }
    text { font-size: 9px; fill: $sub-ink; }
    .prev { stroke: $sub; stroke-dasharray: 4 3; }
    .wick { stroke-width: 2; &.up { stroke: $up; } &.down { stroke: $down; } }
    .body { &.up { fill: $up; } &.down { fill: $down; } }
    > span { font-size: 13px; line-height: 1.5; color: $honey-ink; word-break: keep-all; }
    b.up { color: $up; } b.down { color: $down; }
}
.gl-related {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    button { height: 32px; padding: 0 10px; border: 1px solid $line; border-radius: 8px; background: $card; color: $sub-ink; font-size: 13px; cursor: pointer; }
}
.gl-lesson {
    width: 100%;
    min-height: 44px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-top: 14px;
    padding: 0 14px;
    border: 0;
    border-radius: $radius;
    background: $band;
    color: $ink;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    i { font-style: normal; font-weight: 400; color: $sub; }
}
</style>
