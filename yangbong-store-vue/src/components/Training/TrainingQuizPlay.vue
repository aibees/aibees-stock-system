<template>
    <div id="training-quiz-play">
        <BrandHeader :title="title" :back="QUIZ_PATH" />
        <main class="qp-main">
            <div v-if="!questions.length" class="qp-end">
                <img src="/img/emoji/trophy.png" alt="" width="72" height="72" />
                <h2>{{ emptyText }}</h2>
                <button type="button" class="primary" @click="router.push(QUIZ_PATH)">퀴즈 목록으로</button>
            </div>

            <div v-else-if="finished" class="qp-end">
                <img src="/img/emoji/trophy.png" alt="" width="72" height="72" />
                <h2>{{ questions.length }}문제 중 {{ score }}문제 맞혔어요</h2>
                <p>{{ score === questions.length ? '모두 맞혔어요. 잘하셨어요.' : '틀린 문제는 다시 풀어볼 수 있어요.' }}</p>
                <button v-if="quiz.wrongQuestions.length" type="button" class="primary" @click="retryWrong">틀린 문제 다시 풀기</button>
                <button type="button" class="ghost" @click="router.push(QUIZ_PATH)">퀴즈 목록으로</button>
            </div>

            <template v-else>
                <small class="count">{{ index + 1 }} / {{ questions.length }}</small>
                <div class="bar" role="progressbar" :aria-valuenow="index + 1" aria-valuemin="1" :aria-valuemax="questions.length"><span :style="{ width: `${(index + 1) / questions.length * 100}%` }"></span></div>
                <p v-if="showChapter" class="chapter">{{ current.chapterName }}</p>
                <h2 class="question">{{ current.q }}</h2>

                <div class="options">
                    <button v-for="(opt, i) in current.options" :key="i" type="button" :class="optionClass(i)" :disabled="picked !== null" @click="pick(i)">
                        <span>{{ opt }}</span>
                        <i aria-hidden="true">{{ picked === null ? '' : i === current.answer ? '✓' : i === picked ? '✕' : '' }}</i>
                    </button>
                </div>

                <template v-if="picked !== null">
                    <div class="explain" aria-live="polite">
                        <b>{{ picked === current.answer ? '맞았어요' : '아쉬워요' }}</b>
                        <p>{{ current.explain }}</p>
                    </div>
                    <button type="button" class="primary" @click="goNext">{{ index + 1 < questions.length ? '다음 문제' : '결과 보기' }}</button>
                </template>
            </template>
        </main>
    </div>
</template>

<script setup>
/** 퀴즈 풀기: 한 화면에 한 문제. 고르면 바로 정답·해설을 보여 주고 결과를 기록한다. */
import { allQuestions, quizChapters, QUIZ_PATH, quizSetPath, todayQuestion } from '@scripts/trainingQuiz.js';
import { useQuizStore } from '@scripts/stores/quiz-store.js';

const router = useRouter();
const route = useRoute();
const quiz = useQuizStore();

const setName = computed(() => String(route.params.set ?? ''));
const chapterSet = computed(() => quizChapters().find(c => c.slug === setName.value) ?? null);
const title = computed(() => ({ all: '전체 풀기', wrong: '틀린 문제', today: '오늘의 한 문제' }[setName.value] ?? chapterSet.value?.name ?? '퀴즈'));
const showChapter = computed(() => !chapterSet.value);
const emptyText = computed(() => (setName.value === 'wrong' ? '다시 풀 틀린 문제가 없어요' : '문제를 찾을 수 없어요'));

const load = () => {
    if (setName.value === 'all') return allQuestions();
    if (setName.value === 'wrong') return [...quiz.wrongQuestions];   // 푸는 동안 순서가 바뀌지 않게 시작할 때 고정
    if (setName.value === 'today') return [todayQuestion()].filter(Boolean);
    return chapterSet.value?.questions ?? [];
};

const questions = ref(load());
const index = ref(0);
const picked = ref(null);
const score = ref(0);
const finished = ref(false);
const current = computed(() => questions.value[index.value]);

const reset = () => {
    questions.value = load();
    index.value = 0;
    picked.value = null;
    score.value = 0;
    finished.value = false;
};
watch(setName, reset);

const pick = (i) => {
    picked.value = i;
    const isRight = i === current.value.answer;
    if (isRight) score.value += 1;
    quiz.record(current.value.id, isRight);
    // 오늘의 한 문제를 맞히면 꿀(하루 1번, 서버가 판단)
    if (isRight && setName.value === 'today') import('@scripts/stores/honey-store.js').then(({ useHoneyStore }) => useHoneyStore().quizCorrect());
};
const goNext = () => {
    if (index.value + 1 >= questions.value.length) { finished.value = true; return; }
    index.value += 1;
    picked.value = null;
    window.scrollTo(0, 0);
};
const retryWrong = () => {
    if (setName.value === 'wrong') reset();
    else router.replace(quizSetPath('wrong'));
};
const optionClass = (i) => ({
    right: picked.value !== null && i === current.value.answer,
    wrong: picked.value === i && i !== current.value.answer,
});
</script>

<style scoped lang="scss">
@use '@@/_home-tokens.scss' as *;

#training-quiz-play { min-height: 100vh; background: $card; color: $ink; text-align: left; font-family: $font-body; letter-spacing: -0.2px; -webkit-font-smoothing: antialiased; }
button { width: 100%; border: 0; color: inherit; font: inherit; letter-spacing: inherit; cursor: pointer; -webkit-tap-highlight-color: transparent; }
.qp-main { max-width: 720px; margin: 0 auto; padding: 6px $pad-x 24px; box-sizing: border-box; }
.count { font-size: 13px; font-weight: 600; color: $amber-700; }
.bar { height: 6px; margin-top: 8px; border-radius: 3px; background: $band; overflow: hidden; span { display: block; height: 100%; border-radius: 3px; background: $honey-500; transition: width .2s ease; } }
.chapter { margin: 22px 0 -16px; font-size: 13px; color: $sub; }
.question { margin: 26px 0 18px; font-size: 21px; font-weight: 700; line-height: 1.4; letter-spacing: -0.5px; word-break: keep-all; }
.options { display: flex; flex-direction: column; gap: 8px; }
.options button {
    min-height: 54px;
    padding: 12px 14px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    border: 1px solid $line;
    border-radius: $radius;
    background: $card;
    font-size: 16px;
    text-align: left;
    word-break: keep-all;
    &:disabled { cursor: default; color: $sub; }
    i { flex: none; font-style: normal; font-weight: 700; }
    &.right { border-color: $honey-500; background: $honey-strip; color: $honey-ink; font-weight: 700; i { color: $amber-700; } }
    &.wrong { border-color: $line; background: $band; color: $sub-ink; i { color: $up; } }
}
.explain {
    margin-top: 12px;
    padding: 14px;
    border-radius: $radius;
    background: $band;
    b { font-size: 13px; color: $amber-700; }
    p { margin: 4px 0 0; font-size: 14px; line-height: 1.55; color: $sub-ink; word-break: keep-all; }
}
.primary, .ghost { min-height: 50px; margin-top: 14px; border-radius: $radius; font-size: 16px; font-weight: 700; }
.primary { background: $honey-300; color: $honey-ink; }
.ghost { margin-top: 8px; background: $band; }
.qp-end {
    padding-top: 72px;
    text-align: center;
    img { display: inline-block; }
    h2 { margin: 16px 0 0; font-size: 21px; letter-spacing: -0.5px; }
    p { margin: 8px 0 12px; font-size: 14px; color: $sub; }
}
</style>
