<template>
    <div id="training-lesson">
        <header class="tl-header">
            <button type="button" class="tl-back" :aria-label="chapter ? `${chapter.name} 목차로` : '트레이닝 목차로'" @click="goChapter">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m15 18-6-6 6-6"></path></svg>
            </button>
            <div class="tl-head-text">
                <p v-if="stage" class="tl-crumb">{{ chapter.name }} · {{ stage.indexInChapter }}/{{ chapter.stages.length }}</p>
                <h1>{{ stage ? `${stage.no}. ${stage.title}` : '찾을 수 없는 단계' }}</h1>
            </div>
        </header>

        <main class="tl-main">
            <!-- 없는 단계 -->
            <template v-if="!stage">
                <p class="tl-msg">없는 단계입니다.</p>
                <button type="button" class="tl-cta ghost" @click="router.push(TRAINING_PATH)">목차로 돌아가기</button>
            </template>

            <!-- 본문 준비 중 -->
            <template v-else-if="!stage.lesson">
                <p class="tl-msg">이 단계는 내용을 준비하고 있어요. 준비되면 여기서 이어서 할 수 있습니다.</p>
                <button type="button" class="tl-cta ghost" @click="goChapter">목차로 돌아가기</button>
            </template>

            <!-- 장 끝 확인 문제 -->
            <template v-else-if="stage.isQuiz">
                <p class="tl-lead">이 장에서 익힌 것을 확인합니다. 모두 맞히면 이 장을 마칩니다.</p>
                <ol class="tq-list">
                    <li v-for="(item, qi) in stage.lesson.quiz" :key="qi" class="tq">
                        <p class="tq-q"><span class="tq-no">Q{{ qi + 1 }}.</span> {{ item.q }}</p>
                        <ul class="tq-options">
                            <li v-for="(opt, oi) in item.options" :key="oi">
                                <button type="button" class="tq-option"
                                    :class="{ right: isRight(qi) && oi === item.answer, wrong: picked[qi] === oi && oi !== item.answer }"
                                    :disabled="isRight(qi)" :aria-pressed="picked[qi] === oi" @click="pick(qi, oi)">
                                    <span class="tq-label">{{ opt }}</span>
                                    <span class="tq-mark" aria-hidden="true">{{ isRight(qi) && oi === item.answer ? '✓' : picked[qi] === oi ? '✕' : '' }}</span>
                                </button>
                            </li>
                        </ul>
                        <p v-if="isRight(qi)" class="tq-explain right" aria-live="polite">맞았어요. {{ item.explain }}</p>
                        <p v-else-if="picked[qi] != null" class="tq-explain" aria-live="polite">다시 골라 보세요.</p>
                    </li>
                </ol>
            </template>

            <!-- 읽는 단계 -->
            <article v-else class="tl-body">
                <template v-for="(b, bi) in stage.lesson.body" :key="bi">
                    <h2 v-if="b.h" class="tl-h">{{ b.h }}</h2>
                    <p v-else-if="b.p" class="tl-p">{{ b.p }}</p>
                    <p v-else-if="b.note" class="tl-note">{{ b.note }}</p>
                    <dl v-else-if="b.terms" class="tl-terms">
                        <div v-for="([term, desc], ti) in b.terms" :key="ti"><dt>{{ term }}</dt><dd>{{ desc }}</dd></div>
                    </dl>
                    <TrainingPlay v-else-if="b.play" :name="b.play" />
                    <figure v-else-if="b.figure" class="tl-figure">
                        <TrainingFigure :name="b.figure" />
                        <figcaption v-if="b.caption">{{ b.caption }}</figcaption>
                    </figure>
                </template>
                <p v-if="hasExampleChart" class="tl-fineprint">예시 차트는 설명을 위해 만든 가상 시세입니다.</p>
            </article>

            <!-- 하단: 마치기 / 다음 단계 -->
            <div v-if="stage && stage.lesson" class="tl-foot">
                <template v-if="!store.isDone(stage.key)">
                    <p v-if="stage.isQuiz" class="tl-count">{{ stage.lesson.quiz.length }}문제 중 {{ rightCount }}문제 맞힘</p>
                    <button type="button" class="tl-cta" :disabled="stage.isQuiz && !allRight" @click="finish">
                        {{ stage.isQuiz ? '확인 마치기' : '다 읽었어요' }}
                    </button>
                </template>
                <template v-else>
                    <p class="tl-done">✓ 마친 단계입니다.</p>
                    <button v-if="following && following.lesson" type="button" class="tl-cta" @click="go(following)">다음 단계: {{ following.short || following.title }}</button>
                    <button type="button" class="tl-cta ghost" @click="goChapter">목차로</button>
                </template>
            </div>
        </main>
    </div>
</template>

<script setup>
import TrainingFigure from './TrainingFigure.vue';
import TrainingPlay from './TrainingPlay.vue';
import { findChapter, findStage, followingStage, chapterPath, stagePath, TRAINING_PATH } from '@scripts/training.js';
import { useTrainingStore } from '@scripts/stores/training-store.js';

const router = useRouter();
const route = useRoute();
const store = useTrainingStore();

const stage = computed(() => findStage(String(route.params.chapter ?? ''), String(route.params.stage ?? '')));
const chapter = computed(() => (stage.value ? findChapter(stage.value.chapterSlug) : null));
const following = computed(() => followingStage(stage.value));
const hasExampleChart = computed(() =>
    (stage.value?.lesson?.body ?? []).some(b => ['volume', 'ma', 'sr'].includes(b.figure)));

/* ── 확인 문제: 틀리면 다시 고를 수 있고, 맞힌 문항은 그대로 둔다 ── */
const picked = ref([]);
watch(() => stage.value?.key, () => { picked.value = []; });
const isRight = (qi) => picked.value[qi] != null && picked.value[qi] === stage.value.lesson.quiz[qi].answer;
const pick = (qi, oi) => {
    if (isRight(qi)) return;
    const copy = [...picked.value];
    copy[qi] = oi;
    picked.value = copy;
};
const rightCount = computed(() => (stage.value?.lesson?.quiz ?? []).filter((_, qi) => isRight(qi)).length);
const allRight = computed(() => stage.value?.isQuiz && rightCount.value === stage.value.lesson.quiz.length);

const go = (s) => router.push(stagePath(s));
const goChapter = () => router.push(chapter.value ? chapterPath(chapter.value) : TRAINING_PATH);

/** 마치면 같은 장의 다음 단계로, 장의 마지막(확인)이면 목차의 그 장으로 돌아가 '마침'을 보여 준다. */
const finish = () => {
    if (!store.complete(stage.value.key)) return;
    const f = following.value;
    if (f && f.chapterSlug === stage.value.chapterSlug && f.lesson) router.replace(stagePath(f));
    else router.replace(chapterPath(chapter.value));
};
</script>

<style scoped lang="scss">
@use '@@/_home-tokens.scss' as *;

#training-lesson {
    min-height: 100vh;
    background: $card;
    color: $ink;
    text-align: left;
    font-family: $font-body;
}
.tl-header {
    display: flex;
    align-items: center;
    gap: 2px;
    padding: 6px $pad-x 8px 4px;
    background: $bar;
    border-bottom: 1px solid $line-soft;
    position: sticky;
    top: env(safe-area-inset-top, 0px);
    z-index: 10;

    h1 { margin: 0; font-size: 17px; line-height: 1.35; font-weight: 700; letter-spacing: -0.4px; color: $ink; word-break: keep-all; }
}
.tl-head-text { min-width: 0; padding-top: 2px; }
.tl-crumb { margin: 0 0 1px; font-size: .74rem; color: $sub-2; font-variant-numeric: tabular-nums; }
.tl-back {
    flex: none;
    width: 44px; height: 44px;
    display: inline-flex; align-items: center; justify-content: center;
    background: none; border: 0; color: $brown-ink; cursor: pointer;
}
.tl-main { max-width: 640px; margin: 0 auto; padding: 20px $pad-x 24px; }
.tl-msg, .tl-lead { margin: 0 0 18px; font-size: .95rem; line-height: 1.6; color: $sub; word-break: keep-all; }

/* ── 본문 ── */
.tl-body { word-break: keep-all; }
.tl-p { margin: 0 0 14px; font-size: 1rem; line-height: 1.75; }
.tl-h { margin: 26px 0 10px; font-size: 1.05rem; font-weight: 800; color: $brown-ink; }
.tl-note {
    margin: 0 0 14px; padding: 10px 12px;
    border-radius: 10px; background: $honey-50;
    font-size: .9rem; line-height: 1.65; color: $sub;
}
.tl-terms {
    margin: 0 0 16px; border-top: 1px solid $line-soft;
    div { display: flex; gap: 14px; padding: 10px 0; border-bottom: 1px solid $line-soft; }
    dt { flex: none; width: 4.5em; font-weight: 700; color: $brown-ink; }
    dd { margin: 0; color: $ink; line-height: 1.5; }
}
.tl-figure {
    margin: 8px 0 18px; padding: 14px 0 10px;
    border-top: 1px solid $line-soft; border-bottom: 1px solid $line-soft;
    figcaption { margin-top: 8px; font-size: .82rem; line-height: 1.5; color: $sub-2; text-align: center; }
}
.tl-fineprint { margin: 18px 0 0; font-size: .74rem; color: $sub-2; }

/* ── 확인 문제: 선택지는 온보딩과 같은 구분선 목록, 맞힌 줄은 글자색과 ✓ ── */
.tq-list { list-style: none; margin: 0; padding: 0; }
.tq + .tq { margin-top: 26px; }
.tq-q { margin: 0 0 10px; font-size: 1rem; line-height: 1.55; font-weight: 700; word-break: keep-all; }
.tq-no { color: $amber-700; font-variant-numeric: tabular-nums; }
.tq-options { list-style: none; margin: 0; padding: 0; border-top: 1px solid $line; }
.tq-option {
    width: 100%;
    display: flex; align-items: center; justify-content: space-between; gap: 12px;
    min-height: 52px; padding: 12px 4px;
    border: 0; border-bottom: 1px solid $line;
    background: transparent; color: $ink;
    font: inherit; text-align: left; cursor: pointer;
    -webkit-tap-highlight-color: transparent;
    @media (hover: hover) { &:hover:not(:disabled) { background: $bg; } }
    &:active:not(:disabled) { background: $bar; }
    &:disabled { cursor: default; color: $sub-2; }
    &.right { color: $brown-ink; font-weight: 700; }
    &.wrong { color: $sub-2; .tq-label { text-decoration: line-through; } }
}
.tq-label { font-size: .98rem; line-height: 1.45; word-break: keep-all; }
.tq-mark { flex: none; width: 20px; text-align: center; font-weight: 700; color: $amber-700; }
.tq-option.wrong .tq-mark { color: $sub-2; }
.tq-explain {
    margin: 10px 0 0; font-size: .88rem; line-height: 1.6; color: $sub; word-break: keep-all;
    &.right { color: $brown-ink; }
}

/* ── 하단 ── */
.tl-foot { margin-top: 28px; display: flex; flex-direction: column; gap: 10px; }
.tl-count { margin: 0; font-size: .84rem; color: $sub-2; text-align: center; font-variant-numeric: tabular-nums; }
.tl-done { margin: 0; font-size: .92rem; font-weight: 700; color: $amber-700; text-align: center; }
.tl-cta {
    width: 100%;
    min-height: 52px;
    padding: 0 16px;
    border: 0;
    border-radius: $radius;
    background: $honey-300;
    color: $honey-ink;
    font: inherit;
    font-size: 1rem;
    font-weight: 700;
    cursor: pointer;
    word-break: keep-all;
    transition: transform .1s ease;
    &:active:not(:disabled) { transform: scale(.98); }
    &:disabled { background: $line-soft; color: $sub-2; cursor: default; }
    &.ghost { background: $band; border: 0; color: $ink; }
}
.tl-msg + .tl-cta, .tl-cta + .tl-cta { margin-top: 10px; }

/* 2026-11-17 꿀빛 톤: 맞힌 보기·문항 번호 앰버, 다음 버튼 꿀색 */
.tl-crumb { color: $amber-700; }
.tq-option.right { color: $amber-700; }
.tq-explain.right { color: $honey-ink; }
</style>
