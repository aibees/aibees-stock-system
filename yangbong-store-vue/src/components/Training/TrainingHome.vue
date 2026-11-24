<template>
    <div id="training-home">
        <BrandHeader title="재테크 학습하기" :back="TRAINING_PATH" />

        <main class="tr-main">
            <!-- 코스 고르기 + 코스 진행(장별 막대). 2026-11-24 코스 도입 -->
            <section class="tr-card tr-top" aria-label="코스와 진행 상황">
                <div class="tr-courses" role="tablist">
                    <button v-for="c in courseList" :key="c.slug" type="button" role="tab" class="tr-course"
                        :class="{ on: c.slug === course.slug }" :aria-selected="c.slug === course.slug ? 'true' : 'false'"
                        @click="pickCourse(c)">{{ c.name }}<template v-if="c.free"> · 무료</template></button>
                </div>
                <div class="tr-sum">
                    <div class="tr-sum-top"><b>{{ store.doneIn(course.slug) }} / {{ course.stages.length }}{{ course.unit }}</b><span>{{ course.title }}</span></div>
                    <div v-for="ch in chapterList" :key="ch.slug" class="tr-sum-row">
                        <div class="tr-sum-name"><span>{{ chapterMeta(ch, true) }} · {{ ch.name }}</span><em>{{ doneOf(ch) }}/{{ ch.stages.length }}</em></div>
                        <span class="tr-sum-bar"><span :style="{ width: `${ch.stages.length ? doneOf(ch) / ch.stages.length * 100 : 0}%` }"></span></span>
                    </div>
                </div>
            </section>

            <!-- 장: 펼친 장은 단계 리스트, 접힌 장은 한 줄(누르면 펼침). 기본은 지금 차례인 장만 펼친다 -->
            <section v-for="ch in chapterList" :id="`ch-${ch.slug}`" :key="ch.slug" class="tr-card tr-chapter"
                :class="{ folded: !isExpanded(ch) }">
                <button type="button" class="tr-ch-head" :aria-expanded="isExpanded(ch) ? 'true' : 'false'"
                    :aria-controls="`ch-list-${ch.slug}`" @click="toggleChapter(ch)">
                    <span class="tr-ch-text">
                        <span class="tr-ch-meta">{{ chapterMeta(ch) }}</span>
                        <span class="tr-ch-name">{{ ch.name }}</span>
                    </span>
                    <span class="tr-ch-state" :class="chapterState(ch).cls">
                        {{ chapterState(ch).text }}
                        <svg class="tr-chev" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 9l6 6 6-6"></path></svg>
                    </span>
                </button>

                <ol v-if="isExpanded(ch)" :id="`ch-list-${ch.slug}`" class="tr-list">
                    <li v-for="s in ch.stages" :key="s.key" :class="{ 'tr-quiz-li': s.isQuiz }">
                        <!-- 장 마무리 확인 퀴즈(2026-11-22 개편): 수업 줄과 구분되는 한 덩어리. 문제 수 · 맞힌 수 · 풀기 -->
                        <button v-if="s.isQuiz" type="button" class="tr-quiz" :class="{ done: store.isDone(s.key), now: isNext(s) }"
                            :aria-label="`${quizTitle(s)}, ${quizState(s)}`" @click="openStage(s)">
                            <span class="tr-quiz-ic" aria-hidden="true"><img src="/img/emoji/target.png" alt="" /></span>
                            <span class="tr-text">
                                <b>{{ quizTitle(s) }}</b>
                                <small>{{ quizSub(ch, s) }}</small>
                            </span>
                            <span class="tr-quiz-go" aria-hidden="true">{{ quizState(s) }}</span>
                        </button>
                        <button v-else type="button" class="tr-row" :class="rowCls(s)"
                            :aria-label="`${stageNoText(s)} ${s.title}${rowState(s).label ? `, ${rowState(s).label}` : ''}`"
                            @click="openStage(s)">
                            <span class="tr-no" aria-hidden="true">
                                <svg v-if="store.isDone(s.key)" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="m5 12.5 4.5 4.5L19 7.5"></path></svg>
                                <template v-else>{{ s.indexInChapter }}</template>
                            </span>
                            <span class="tr-text">
                                <b>{{ shortOf(s) }}</b>
                                <small v-if="s.sub">{{ s.sub }}</small>
                            </span>
                            <span v-if="s.basis && course.basis" class="tr-basis" aria-hidden="true">{{ basisShort }} 기준</span>
                            <span class="tr-state" aria-hidden="true">{{ rowState(s).label }}</span>
                        </button>
                    </li>
                </ol>
            </section>

            <section v-if="soon.length" class="tr-card tr-soon">
                <p class="tr-soon-title">곧 추가돼요</p>
                <ul class="tr-soon-list">
                    <li v-for="name in soon" :key="name">{{ name }}</li>
                </ul>
            </section>

            <p class="tr-note">설명용 자료이며 특정 종목의 매수·매도를 권하지 않습니다. 투자 판단과 책임은 본인에게 있습니다.</p>
        </main>
    </div>
</template>

<script setup>
/**
 * 수업 목록(/training/lessons, /training/<장>): 장별 1열 단계 리스트.
 *   - 목록 줄은 짧은 제목(short) + 회색 한 줄 설명(sub). 긴 원래 제목(title)은 레슨 화면에서만 쓴다.
 *   - 기본으로 지금 차례인 장(또는 /training/:chapter 로 들어온 장)만 펼친다. 다른 장은 한 줄로 접혀 있고 누르면 펼친다.
 */
import { courses, findCourse, findChapter, stageNoText, soonItems, stagePath, TRAINING_PATH } from '@scripts/training.js';
import { useTrainingStore } from '@scripts/stores/training-store.js';
import { useQuizStore } from '@scripts/stores/quiz-store.js';

const router = useRouter();
const route = useRoute();
const store = useTrainingStore();
const quiz = useQuizStore();


/* ── 코스: ?course= → /training/<장> 의 장이 속한 코스 → 마지막으로 연 코스 ── */
const courseList = courses();
const course = computed(() => findCourse(String(route.query.course ?? ''))
    ?? findCourse(findChapter(String(route.params.chapter ?? ''))?.course)
    ?? findCourse(store.lastCourse) ?? courseList[0]);
watch(() => course.value.slug, (c) => store.useCourse(c), { immediate: true });
const pickCourse = (c) => router.replace({ path: '/training/lessons', query: { course: c.slug } });
const chapterList = computed(() => course.value.chapters);
const soon = soonItems();
const next = computed(() => store.nextIn(course.value.slug));
const doneOf = (ch) => ch.stages.filter(s => store.isDone(s.key)).length;
/** 장 머리글: 경제 기초 '1단계 · 1–7강', 투자 실전 '1장 · 단계 1–6' */
const chapterMeta = (ch, short = false) => (course.value.unit === '강'
    ? (short ? `${ch.no}단계` : `${ch.no}단계 · ${ch.first}–${ch.last}강`)
    : (short ? `${ch.no}장` : `${ch.no}장 · 단계 ${ch.first}–${ch.last}`));
const basisShort = computed(() => { const [, m, d] = (course.value.basis ?? '').split('-'); return m ? `${Number(m)}.${Number(d)}` : ''; });

const shortOf = (s) => s.short || s.title;
const isNext = (s) => next.value?.key === s.key;
const openStage = (s) => router.push(stagePath(s));

/* ── 펼침: 지금 차례 장 + 주소로 고른 장. 사용자가 누르면 그 장만 토글 ── */
const defaultOpen = () => {
    const set = new Set();
    if (next.value) set.add(next.value.chapterSlug);
    else if (chapterList.value.length) set.add(chapterList.value[0].slug);
    if (route.params.chapter) set.add(String(route.params.chapter));
    return set;
};
const expanded = ref(defaultOpen());
watch(() => course.value.slug, () => { expanded.value = defaultOpen(); });
const isExpanded = (ch) => expanded.value.has(ch.slug);
const toggleChapter = (ch) => {
    const s = new Set(expanded.value);
    s.has(ch.slug) ? s.delete(ch.slug) : s.add(ch.slug);
    expanded.value = s;
};
// 전체 메뉴의 장 바로가기로 같은 화면 안에서 장을 바꾸면 그 장을 펼친다(스크롤은 라우터 scrollBehavior)
watch(() => route.params.chapter, (slug) => {
    if (slug && !expanded.value.has(String(slug))) expanded.value = new Set([...expanded.value, String(slug)]);
});

// 장 오른쪽 표시: 마친 수 / 다 마침.
const chapterState = (ch) => {
    const n = ch.stages.filter(s => store.isDone(s.key)).length;
    if (n === ch.stages.length) return { text: '✓ 마침', cls: 'all' };
    return { text: `${n}/${ch.stages.length}`, cls: 'now' };
};

// 단계 줄 상태: 마침 / 지금(안 마친 첫 단계) / 그 밖에는 표시 없음
const rowState = (s) => {
    if (store.isDone(s.key)) return { label: '마침' };
    if (!s.lesson) return { label: '준비 중' };
    if (isNext(s)) return { label: '지금 ›' };
    return { label: '' };
};
/* 확인 퀴즈 줄: '기초 확인 퀴즈' · 'N문제 · 수업 3/5 마침' · 맞힌 수 또는 풀기 */
const quizTitle = (s) => { const t = shortOf(s); return t.includes('퀴즈') ? t : `${t} 퀴즈`; };
const quizIds = (s) => (s.lesson?.quiz ?? []).map((_, i) => `${s.key}#${i}`);
const quizSub = (ch, s) => {
    const lessons = ch.stages.filter(x => !x.isQuiz);
    const done = lessons.filter(x => store.isDone(x.key)).length;
    return `${quizIds(s).length}문제 · 수업 ${done}/${lessons.length} 마침`;
};
const quizState = (s) => {
    const ids = quizIds(s);
    const tried = ids.filter(id => quiz.results[id]).length;
    if (!tried) return '풀기 ›';
    return `${ids.filter(id => quiz.results[id] === 'right').length}/${ids.length} 맞힘`;
};

const rowCls = (s) => ({
    done: store.isDone(s.key),
    now: isNext(s),
});
</script>

<style scoped lang="scss">
@use '@@/_home-tokens.scss' as *;

// 2026-11-17 화이트 톤: 흰 판 + 연회색 띠. 단계는 1열 리스트(번호 · 짧은 제목/설명 · 상태 하나).
#training-home {
    min-height: 100vh;
    background: $band;
    color: $ink;
    text-align: left;
    font-family: $font-body;
    letter-spacing: -0.2px;
    -webkit-font-smoothing: antialiased;
}
button { font: inherit; letter-spacing: inherit; }

.tr-main {
    max-width: 720px;
    margin: 0 auto;
    padding: 0 0 24px;
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
    gap: $band-h;
}
.tr-card { background: $card; padding: 24px $pad-x; }

/* ── 전체 진행 ── */
.tr-top { padding-top: 8px; padding-bottom: 20px; }
.tr-prog { display: flex; align-items: center; gap: 10px; }
.tr-bar {
    flex: 1; height: 6px; border-radius: 3px; background: $band; overflow: hidden;
    span { display: block; height: 100%; min-width: 6px; border-radius: 3px; background: $honey-dot; transition: width .3s ease; }
}
.tr-prog-count { flex: none; font-size: 13px; color: $sub; font-variant-numeric: tabular-nums; b { color: $amber-700; font-weight: 700; } }

/* ── 장 ── */
.tr-chapter.folded { padding-top: 8px; padding-bottom: 8px; }
.tr-ch-head {
    width: 100%;
    min-height: 56px;
    display: flex;
    align-items: flex-end;
    gap: 10px;
    padding: 0;
    border: 0;
    background: transparent;
    color: inherit;
    text-align: left;
    cursor: pointer;
    -webkit-tap-highlight-color: transparent;
}
.folded .tr-ch-head { align-items: center; }
.tr-ch-text { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 4px; }
.tr-ch-meta { font-size: 13px; color: $sub; font-variant-numeric: tabular-nums; }
.tr-ch-name { font-size: 20px; font-weight: 700; letter-spacing: -0.5px; color: $ink; word-break: keep-all; }
.folded .tr-ch-name { font-size: 17px; font-weight: 600; letter-spacing: -0.4px; }
.folded.locked .tr-ch-name { color: $sub-ink; }
.tr-ch-state {
    flex: none;
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding-bottom: 2px;
    font-size: 13px;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
    color: $ink;
    &.now, &.all { color: $amber-700; }
    &.locked { color: $sub-2; font-weight: 500; }
}
.tr-chev { width: 16px; height: 16px; color: $sub-2; transition: transform .15s ease; }
.tr-ch-head[aria-expanded="true"] .tr-chev { transform: rotate(180deg); }
.tr-lock { width: 14px; height: 14px; fill: $sub-2; }

/* ── 단계 리스트 ── */
.tr-list { list-style: none; margin: 10px 0 0; padding: 0; }
.tr-row {
    width: 100%;
    min-height: 64px;
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 0;
    border: 0;
    background: transparent;
    color: $ink;
    text-align: left;
    cursor: pointer;
    -webkit-tap-highlight-color: transparent;
    &.locked { cursor: default; }
}
.tr-no {
    flex: none;
    width: 28px;
    height: 28px;
    border-radius: 14px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    background: $band;
    color: $sub-ink;
    font-size: 13px;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
    svg { width: 14px; height: 14px; }
}
.tr-text {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 3px;
    b { font-size: 16px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    small { font-size: 13px; color: $sub; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
}
/* ── 확인 퀴즈 ── */
.tr-quiz-li { margin-top: 10px; }
.tr-quiz {
    width: 100%;
    min-height: 72px;
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 14px;
    border: 0;
    border-radius: $radius;
    background: $honey-strip;
    color: $ink;
    text-align: left;
    cursor: pointer;
    -webkit-tap-highlight-color: transparent;
    .tr-text b { font-weight: 700; }
    .tr-text small { color: $sub-ink; }
}
.tr-quiz-ic {
    flex: none;
    width: 44px;
    height: 44px;
    border-radius: $radius;
    background: $card;
    display: flex;
    align-items: center;
    justify-content: center;
    img { width: 30px; height: 30px; display: block; }
}
.tr-quiz-go {
    flex: none;
    height: 34px;
    padding: 0 12px;
    border-radius: 8px;
    background: $honey-300;
    color: $honey-ink;
    display: inline-flex;
    align-items: center;
    font-size: 13px;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
}
.tr-quiz.done .tr-quiz-go { background: $card; color: $amber-700; }

.tr-state { flex: none; display: inline-flex; align-items: center; font-size: 13px; color: $sub; }

.tr-row.done {
    .tr-no { background: $honey-dot; color: $honey-ink; }
    .tr-state { color: $sub-ink; }
}
.tr-row.now {
    .tr-no { background: $card; box-shadow: inset 0 0 0 1.5px $amber-700; color: $amber-700; }
    .tr-state { color: $amber-700; font-weight: 600; }
}
.tr-row.locked {
    .tr-no { background: transparent; box-shadow: inset 0 0 0 1px $line; color: $sub-2; }
    .tr-text b { color: $sub; font-weight: 500; }
    .tr-text small { color: $sub-2; }
}

/* ── 곧 추가 ── */
.tr-soon-title { margin: 0 0 8px; font-size: 14px; font-weight: 600; color: $sub; }
.tr-soon-list {
    list-style: none; margin: 0; padding: 0; display: flex; flex-wrap: wrap; gap: 6px;
    li { height: 30px; padding: 0 12px; border-radius: 8px; background: $honey-50; font-size: 13px; color: $sub; display: inline-flex; align-items: center; }
}

.tr-note { margin: 0; padding: 12px $pad-x 8px; font-size: 12px; line-height: 1.6; color: $sub-2; }


/* ══ 2026-11-24 코스 고르기 · 장별 진행 막대 · 기준일 ══ */
.tr-courses { display: flex; gap: 8px; }
.tr-course { height: 36px; padding: 0 14px; border: 0; border-radius: 10px; background: $band; color: $sub-ink; font: inherit; font-size: 14px; font-weight: 600; cursor: pointer;
    &.on { background: $honey-300; color: $honey-ink; } }
.tr-sum { margin-top: $gap; padding: $card-pad; border: 1px solid $line; border-radius: $radius; }
.tr-sum-top { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; b { font-size: 15px; } span { font-size: 13px; color: $sub; } }
.tr-sum-row { margin-top: $gap; }
.tr-sum-name { display: flex; justify-content: space-between; gap: 8px; font-size: 13.5px; color: $sub-ink; em { font-style: normal; font-size: 13px; color: $sub; font-variant-numeric: tabular-nums; } }
.tr-sum-bar { display: block; height: 6px; margin-top: 6px; border-radius: 3px; background: $band; overflow: hidden; span { display: block; height: 100%; border-radius: 3px; background: $honey-500; } }
.tr-basis { flex: none; margin-left: auto; padding: 2px 6px; border-radius: 6px; background: $down-bg; color: $down; font-size: 11px; font-weight: 700; white-space: nowrap; }
.tr-basis + .tr-state { margin-left: 8px; }
</style>
