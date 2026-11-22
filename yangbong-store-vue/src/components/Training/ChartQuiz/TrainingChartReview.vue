<template>
    <div id="chart-quiz-review" class="cr-page">
        <BrandHeader title="다른 방향이었던 문제" :back="TRAINING_PATH" />
        <main class="cr-main">
            <p v-if="!loggedIn" class="cr-msg">로그인하면 지난 문제를 볼 수 있어요.</p>
            <p v-else-if="loading" class="cr-msg">불러오고 있어요</p>
            <section v-else-if="locked" class="cr-lock">
                <h2>구독하면 지난 문제를 다시 풀 수 있어요</h2>
                <p>다른 방향이었던 문제를 다시 보면서, 그때 놓친 신호를 확인해 보세요.</p>
                <button type="button" class="cr-btn" @click="router.push('/honey')">구독하기</button>
            </section>
            <p v-else-if="error" class="cr-msg">{{ error }}</p>
            <p v-else-if="!items.length" class="cr-msg">다시 볼 문제가 없어요.</p>
            <ul v-else>
                <li v-for="it in items" :key="it.questionId">
                    <button type="button" @click="router.push({ path: CHART_QUIZ_PATH, query: { q: it.questionId } })">
                        <b>{{ it.patternName }}</b>
                        <small>Lv.{{ it.level }} · 내 선택 {{ choiceLabel(it.answer) }} · {{ dateText(it.answeredAt) }}</small>
                        <i aria-hidden="true">›</i>
                    </button>
                </li>
            </ul>
        </main>
    </div>
</template>

<script setup>
/** 다시 풀기 목록(구독 전용, 명세 8장). 다른 방향이었던 문제만. 다시 풀어도 점수는 처음 기록만 남는다. */
import { assUserSession } from '@scripts/stores/user-stores';
import { TRAINING_PATH } from '@scripts/training.js';
import { CHART_QUIZ_PATH, choiceLabel, fetchHistory, errorCode } from '@scripts/trainingChart.js';

const router = useRouter();
const loggedIn = computed(() => !!assUserSession().user.accessToken);
const loading = ref(false);
const locked = ref(false);
const error = ref('');
const items = ref([]);

const dateText = (ms) => {
    const d = new Date(ms);
    return `${d.getMonth() + 1}월 ${d.getDate()}일`;
};

onMounted(async () => {
    if (!loggedIn.value) return;
    loading.value = true;
    try {
        items.value = (await fetchHistory()) ?? [];
    } catch (e) {
        if (errorCode(e) === 'SUBSCRIPTION_REQUIRED') locked.value = true;
        else error.value = '목록을 불러오지 못했어요.';
    } finally {
        loading.value = false;
    }
});
</script>

<style scoped lang="scss">
.cr-page { min-height: 100vh; background: #FAF7F0; color: #443D2E; text-align: left; font-family: 'Pretendard', -apple-system, 'Apple SD Gothic Neo', sans-serif; }
.cr-main { max-width: 520px; margin: 0 auto; padding: 4px 18px 32px; box-sizing: border-box; }
.cr-msg { padding: 64px 0; text-align: center; font-size: 14px; color: #8A7F6A; }
.cr-lock {
    padding: 48px 0 0;
    text-align: center;
    h2 { margin: 0; font-size: 19px; font-weight: 800; color: #2A2419; word-break: keep-all; }
    p { margin: 8px 0 20px; font-size: 14px; line-height: 1.65; color: #8A7F6A; word-break: keep-all; }
}
.cr-btn { width: 100%; min-height: 52px; border: 0; border-radius: 14px; background: #D99800; color: #fff; font: inherit; font-size: 16px; font-weight: 800; cursor: pointer; }
ul { margin: 0; padding: 0; list-style: none; }
li button {
    width: 100%;
    min-height: 64px;
    display: grid;
    grid-template-columns: 1fr auto;
    align-items: center;
    padding: 10px 0;
    border: 0;
    border-bottom: 1px solid #EDE6D6;
    background: transparent;
    color: inherit;
    font: inherit;
    text-align: left;
    cursor: pointer;
    b { grid-column: 1; font-size: 15px; font-weight: 700; color: #2A2419; }
    small { grid-column: 1; margin-top: 2px; font-size: 12px; color: #8A7F6A; }
    i { grid-column: 2; grid-row: 1 / span 2; font-style: normal; color: #A1927A; }
}
</style>
