<template>
    <div id="training-glossary">
    <BrandHeader title="용어 사전" :back="TRAINING_PATH" />
    <section class="gl" aria-label="주식 용어 사전">
        <label class="gl-search">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><circle cx="11" cy="11" r="7"></circle><path d="m20 20-3.5-3.5"></path></svg>
            <span class="sr-only">용어 검색</span>
            <input v-model="query" type="search" placeholder="용어를 검색해 보세요" autocomplete="off" />
            <button v-if="query" type="button" class="gl-clear" aria-label="검색어 지우기" @click="query = ''">×</button>
        </label>

        <div class="gl-views" role="tablist" aria-label="보기 방식">
            <button v-for="v in VIEWS" :key="v.key" type="button" role="tab" :class="{ on: v.key === view }"
                :aria-selected="v.key === view ? 'true' : 'false'" @click="setView(v.key)">{{ v.label }}</button>
        </div>

        <div class="gl-chips" role="group" :aria-label="view === 'topic' ? '용어 주제' : view === 'mine' ? '내 표시' : '용어 분류'">
            <button v-for="c in chips" :key="c" type="button" :class="{ on: c === category }"
                :aria-pressed="c === category ? 'true' : 'false'" @click="category = c">
                {{ c }}<em v-if="view === 'topic' && c !== ALL">{{ topicCount[c] || 0 }}</em>
            </button>
        </div>

        <p class="gl-count">{{ countText }}</p>

        <p v-if="!groups.length" class="gl-empty">{{ emptyText }}</p>

        <div v-for="g in groups" :key="g.name">
            <h2 class="gl-group">{{ g.name }}</h2>
            <article v-for="t in g.items" :id="`term-${t.id}`" :key="t.id" class="gl-term" :class="{ open: openId === t.id }">
                <button type="button" class="gl-row" :aria-expanded="openId === t.id ? 'true' : 'false'"
                    :aria-controls="`term-body-${t.id}`" @click="toggle(t.id)">
                    <span class="gl-text">
                        <b>{{ t.term }}
                            <i v-if="notes.isFav(t.id)" class="mk fav" title="즐겨찾기">★</i>
                            <i v-if="notes.isConfused(t.id)" class="mk confused" title="헷갈려요">?</i>
                            <i v-if="notes.isKnown(t.id)" class="mk known" title="알아요">✓</i>
                        </b>
                        <small>{{ t.short }}</small>
                    </span>
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

                    <!-- 내 표시: 이 기기에만 저장 -->
                    <div class="gl-mine" role="group" aria-label="내 표시">
                        <button type="button" :class="{ on: notes.isFav(t.id) }" :aria-pressed="notes.isFav(t.id) ? 'true' : 'false'"
                            @click="notes.toggleFav(t.id)"><span aria-hidden="true">{{ notes.isFav(t.id) ? '★' : '☆' }}</span>즐겨찾기</button>
                        <button type="button" :class="{ on: notes.isConfused(t.id), warn: true }" :aria-pressed="notes.isConfused(t.id) ? 'true' : 'false'"
                            @click="notes.toggleConfused(t.id); syncReview(t)"><span aria-hidden="true">?</span>헷갈려요</button>
                        <button type="button" :class="{ on: notes.isKnown(t.id) }" :aria-pressed="notes.isKnown(t.id) ? 'true' : 'false'"
                            @click="notes.toggleKnown(t.id); syncReview(t)"><span aria-hidden="true">✓</span>알아요</button>
                    </div>
                </div>
            </article>
        </div>
    </section>
    </div>
</template>

<script setup>
/**
 * 트레이닝 > 용어 사전: 검색 · 분류/주제/내 단어장 · 가나다 목록. 항목은 한 번에 하나만 펼친다.
 *   분류 = 용어의 성격(차트·기업분석 …), 주제 = 배우는 갈래(경제 첫걸음 · 세금과 절세 …) — glossaryTopics.json
 *   내 단어장 = 즐겨찾기 · 헷갈려요 · 알아요. 이 기기에만 저장된다(glossaryNotes.js).
 */
import { allStages, stagePath, TRAINING_PATH } from '@scripts/training.js';
import { glossaryCategories, categoryGroupOf, glossaryTerms, glossaryTopics, topicOf, groupOf, matchesTerm } from '@scripts/glossary.js';
import { useGlossaryNotes } from '@scripts/glossaryNotes.js';
import { useReviewStore } from '@scripts/stores/review-store.js';

const ALL = '전체';
const VIEWS = [
    { key: 'category', label: '분류' },
    { key: 'topic', label: '주제' },
    { key: 'mine', label: '내 단어장' },
];
const MINE = ['즐겨찾기', '헷갈려요', '알아요'];

const router = useRouter();
const terms = glossaryTerms();
const notes = useGlossaryNotes();

const view = ref('category');
// 트레이닝 첫 화면의 용어 검색(?q=)으로 들어오면 그 말로 찾아 둔다(2026-11-24)
const query = ref(String(useRoute().query.q ?? ''));
const category = ref(ALL);      // 현재 보기(view)에서 고른 칩
const review = useReviewStore();
/** 내 단어장의 '헷갈려요'를 트레이닝 다시 보기(복습)와 맞춘다 — 켜면 복습 목록에 담고, 끄거나 '알아요'면 뺀다 */
const syncReview = (t) => {
    if (notes.isConfused(t.id) !== review.isConfusing(t.term)) review.toggleTerm(t.term, t.easy || t.short, '용어 사전');
};
const openId = ref(null);

const topicCount = computed(() => {
    const m = {};
    terms.forEach((t) => { const k = topicOf(t); m[k] = (m[k] ?? 0) + 1; });
    return m;
});
const chips = computed(() => {
    // 용어가 아직 없는 주제는 칩에서 숨긴다(첫 용어를 넣으면 저절로 나타난다)
    if (view.value === 'topic') return [ALL, ...glossaryTopics().filter(k => topicCount.value[k])];
    if (view.value === 'mine') return [ALL, ...MINE];
    return [ALL, ...glossaryCategories()];
});
const isMarked = (id) => notes.isFav(id) || notes.isConfused(id) || notes.isKnown(id);
const fitsPick = (t) => {
    const c = category.value;
    if (view.value === 'topic') return c === ALL || topicOf(t) === c;
    if (view.value === 'mine') {
        if (c === '즐겨찾기') return notes.isFav(t.id);
        if (c === '헷갈려요') return notes.isConfused(t.id);
        if (c === '알아요') return notes.isKnown(t.id);
        return isMarked(t.id);
    }
    return c === ALL || categoryGroupOf(t) === c;
};
const setView = (key) => { view.value = key; category.value = ALL; openId.value = null; };

const filtered = computed(() => terms.filter(t => fitsPick(t) && matchesTerm(t, query.value)));

const groups = computed(() => {
    const out = [];
    filtered.value.forEach((t) => {
        const name = groupOf(t.term);
        if (out.at(-1)?.name !== name) out.push({ name, items: [] });
        out.at(-1).items.push(t);
    });
    return out;
});

const countText = computed(() => {
    if (query.value.trim()) return `검색 결과 ${filtered.value.length}개`;
    const base = view.value === 'mine' && category.value === ALL ? '내 표시' : category.value;
    return `${base} ${filtered.value.length}개 · 가나다순`;
});

const emptyText = computed(() => {
    if (query.value.trim()) return '찾는 용어가 없어요. 다른 말로 검색해 보세요.';
    if (view.value === 'mine') return '아직 표시한 용어가 없어요. 용어를 펼쳐 맨 아래 버튼으로 표시해 보세요.';
    return '용어가 없어요.';
});

// 검색 결과가 하나면 바로 펼친다
watch(filtered, (list) => {
    if (query.value.trim() && list.length === 1) openId.value = list[0].id;
}, { immediate: true });   // 트레이닝 첫 화면 검색(?q=)으로 들어올 때도

const toggle = (id) => { openId.value = openId.value === id ? null : id; };
const relatedOf = (t) => (t.related ?? []).map(name => terms.find(x => x.term === name)).filter(Boolean);
const lessonOf = (t) => (t.lesson ? allStages().find(s => s.key === t.lesson) ?? null : null);

const openRelated = async (t) => {
    query.value = '';
    view.value = 'category';
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
#training-glossary { min-height: 100vh; background: $card; color: $ink; text-align: left; font-family: $font-body; letter-spacing: -0.2px; -webkit-font-smoothing: antialiased; }
.gl { max-width: 720px; margin: 0 auto; padding-bottom: 12px; }

.gl-search {
    display: flex;
    align-items: center;
    gap: 8px;
    height: 44px;
    margin: 4px $pad-x 0;
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

.gl-views {
    display: flex;
    gap: 4px;
    margin: 12px $pad-x 0;
    padding: 3px;
    border-radius: $radius;
    background: $band;
    button {
        flex: 1;
        height: 34px;
        border: 0;
        border-radius: 8px;
        background: transparent;
        color: $sub;
        font-size: 14px;
        cursor: pointer;
        &.on { background: $card; color: $ink; font-weight: 700; box-shadow: 0 1px 2px rgba(0, 0, 0, .08); }
    }
}
.gl-chips {
    display: flex;
    gap: 4px;
    padding: 10px $pad-x;
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
        em { margin-left: 4px; font-style: normal; font-size: 12px; opacity: .7; }
    }
}
.gl-count { margin: 0; padding: 2px $pad-x 4px; font-size: 13px; color: $sub; }
.gl-empty { margin: 0; padding: 48px $pad-x; text-align: center; font-size: 14px; color: $sub; }
.gl-group { margin: 0; padding: 18px $pad-x 2px; font-size: 13px; font-weight: 700; color: $amber-700; }

.gl-term { margin: 0 $pad-x; border-bottom: 1px solid $line; scroll-margin-top: 64px; &:last-child { border-bottom: 0; } }
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
.gl-text b .mk {
    margin-left: 4px;
    font-style: normal;
    font-size: 12px;
    font-weight: 700;
    &.fav { color: #E0A100; }
    &.confused { color: $amber-700; }
    &.known { color: #2E8B57; }
}
.gl-mine {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 6px;
    margin-top: 16px;
    padding-top: 14px;
    border-top: 1px solid $line;
    button {
        min-height: 52px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 2px;
        padding: 4px 2px;
        border: 1px solid $line;
        border-radius: 10px;
        background: $card;
        color: $sub-ink;
        font-size: 12px;
        cursor: pointer;
        span { font-size: 16px; line-height: 1; }
        &.on { background: $honey-300; border-color: $honey-300; color: $honey-ink; font-weight: 700; }
        &.warn.on { background: $honey-strip; border-color: $amber-700; color: $amber-700; }
    }
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
