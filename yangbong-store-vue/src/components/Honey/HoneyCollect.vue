<template>
    <div id="honey-collect">
        <BrandHeader title="꿀 모으기" back="/menu" />
        <main class="hc">
            <section v-if="!loggedIn" class="guest">
                <img src="/img/emoji/honey.png" alt="" />
                <h2>로그인하고 꿀을 모아 보세요</h2>
                <p>출석, 수업, 오늘의 문제, 광고로 꿀이 쌓이고, 꿀로 프리미엄을 열 수 있어요.</p>
                <button type="button" class="btn" @click="router.push('/login')">로그인</button>
            </section>

            <p v-else-if="!s && honey.loading" class="msg">꿀 정보를 불러오고 있어요</p>
            <p v-else-if="!s" class="msg">꿀 정보를 불러오지 못했어요. 잠시 후 다시 열어 주세요.</p>

            <template v-else>
                <button type="button" class="top" @click="router.push(HONEY_HISTORY_PATH)">
                    <span class="l"><img src="/img/emoji/honey.png" alt="" /><b>{{ fmt(s.balance) }}꿀</b><em>내역 ›</em></span>
                    <small>{{ honey.allDone ? '오늘 꿀을 다 모았어요' : `오늘 ${fmt(s.today.earned)} / ${fmt(s.today.target)}꿀` }}</small>
                    <span class="bar"><i :style="{ width: pct + '%' }"></i></span>
                </button>

                <!-- 오늘의 한 문제: 이 화면에서 바로 푼다 -->
                <section v-if="today" class="quiz">
                    <p class="k">오늘의 한 문제 · +{{ s.quiz.amount }}</p>
                    <p class="q">{{ today.q }}</p>
                    <button v-for="(o, i) in today.options" :key="i" type="button" class="o" :class="optClass(i)"
                        :disabled="answered" @click="answer(i)">
                        <span>{{ o }}</span><i aria-hidden="true">{{ answered ? (i === today.answer ? '✓' : (i === picked ? '✕' : '')) : '' }}</i>
                    </button>
                    <p v-if="answered && picked !== today.answer && !s.quiz.done" class="retry">아쉬워요. 내일 새 문제로 다시 도전해요.</p>
                </section>

                <!-- 연속 출석: 벌집 7칸 -->
                <section class="streak">
                    <p class="t"><span>연속 출석 {{ s.streak.days }}일째</span><em>{{ s.streak.goal }}일째 +{{ s.streak.bonus }}</em></p>
                    <div class="hexes">
                        <span v-for="n in s.streak.goal" :key="n" class="hex"
                            :class="{ f: n <= filled, today: n === filled && s.attend.done, big: n === s.streak.goal }">
                            {{ n === s.streak.goal ? `+${s.streak.bonus}` : n }}
                        </span>
                    </div>
                </section>

                <section class="tasks">
                    <div class="task">
                        <span class="ic">📅</span>
                        <div class="tx"><b>출석 체크</b><small>하루 첫 방문</small></div>
                        <button v-if="s.attend.done" type="button" class="sm done" disabled>완료</button>
                        <button v-else type="button" class="sm" :disabled="honey.busy" @click="honey.attend()">+{{ s.attend.amount }} 받기</button>
                    </div>
                    <div class="task">
                        <span class="ic">▶</span>
                        <div class="tx"><b>광고 보고 꿀 받기</b>
                            <small v-if="!honey.adSupported">앱에서 받을 수 있어요</small>
                            <small v-else-if="adLeft">오늘 {{ adLeft }}번 더 받을 수 있어요</small>
                            <small v-else>내일 다시 받을 수 있어요</small>
                        </div>
                        <button v-if="honey.adSupported && adLeft" type="button" class="sm" :disabled="honey.busy" @click="watchAd">+{{ s.ad.next }} 받기</button>
                        <button v-else type="button" class="sm done" disabled>{{ honey.adSupported ? '완료' : '앱 전용' }}</button>
                    </div>
                    <div class="task">
                        <span class="ic">📚</span>
                        <div class="tx"><b>수업 듣기</b><small>단계마다 +{{ s.lesson.amount }} · {{ s.lesson.done }} / {{ s.lesson.total }}</small></div>
                        <button v-if="s.lesson.done < s.lesson.total" type="button" class="sm" @click="router.push(LESSONS_PATH)">듣기</button>
                        <button v-else type="button" class="sm done" disabled>완료</button>
                    </div>
                    <div v-if="!s.start.done" class="task">
                        <span class="ic">🐝</span>
                        <div class="tx"><b>처음 시작하기</b><small>질문 3개 답하고 종목 담기</small></div>
                        <button type="button" class="sm" @click="router.push(START_PATH)">+{{ s.start.amount }}</button>
                    </div>
                    <div class="task">
                        <span class="ic">💌</span>
                        <div class="tx"><b>친구 초대하기</b><small>곧 열려요 · 친구가 가입하고 3일 방문하면 +300</small></div>
                        <button type="button" class="sm done" disabled>준비 중</button>
                    </div>
                </section>
                <p v-if="adMsg" class="msg small">{{ adMsg }}</p>
                <p class="foot">꿀은 양봉상회 안에서만 쓸 수 있어요. 돈으로 바꾸거나 다른 사람에게 줄 수 없고, 모은 날로부터 1년 뒤 사라져요.</p>
            </template>
        </main>
    </div>
</template>

<script setup>
/** 꿀 모으기 — 오늘의 한 문제, 벌집 출석판, 할 일 목록. 기획: docs/points-plan.md */
import { useHoneyStore } from '@scripts/stores/honey-store.js';
import { assUserSession } from '@scripts/stores/user-stores.js';
import { HONEY_HISTORY_PATH } from '@scripts/support.js';
import { LESSONS_PATH } from '@scripts/training.js';
import { todayQuestion } from '@scripts/trainingQuiz.js';
import { ONBOARDING_PATH } from '@scripts/authPaths.js';

const START_PATH = ONBOARDING_PATH;
const router = useRouter();
const honey = useHoneyStore();
const loggedIn = computed(() => !!assUserSession().user.accessToken);
const s = computed(() => honey.summary);
const fmt = (n) => Number(n ?? 0).toLocaleString();
const pct = computed(() => (s.value ? Math.min(100, Math.round((s.value.today.earned / (s.value.today.target || 1)) * 100)) : 0));
const adLeft = computed(() => (s.value ? Math.max(0, s.value.ad.max - s.value.ad.count) : 0));
// 벌집: 이번 7일 묶음에서 채운 칸 수(연속 일수를 7로 나눈 나머지, 7의 배수 날은 7칸 다)
const filled = computed(() => {
    const d = s.value?.streak?.days ?? 0;
    const g = s.value?.streak?.goal ?? 7;
    return d === 0 ? 0 : (d % g === 0 ? g : d % g);
});

const today = todayQuestion();
const picked = ref(null);
const answered = computed(() => picked.value !== null || !!s.value?.quiz?.done);
const optClass = (i) => (!answered.value ? '' : (i === today.answer ? 'right' : (i === picked.value ? 'wrong' : '')));
const answer = (i) => {
    picked.value = i;
    if (i === today.answer) honey.quizCorrect();
};

const adMsg = ref('');
const watchAd = async () => {
    adMsg.value = '';
    const r = await honey.watchAd();
    if (r === 'dismissed') adMsg.value = '광고를 끝까지 보면 꿀이 쌓여요.';
    else if (r === 'failed') adMsg.value = '광고를 불러오지 못했어요. 잠시 후 다시 해 주세요.';
};

onMounted(() => { if (loggedIn.value) honey.load(); });
</script>

<style scoped lang="scss">
@use '@@/_home-tokens.scss' as *;

#honey-collect { min-height: 100vh; background: $card; color: $ink; text-align: left; font-family: $font-body; letter-spacing: -0.2px; }
button { font: inherit; letter-spacing: inherit; cursor: pointer; }
.hc { max-width: 560px; margin: 0 auto; padding: 4px $pad-x 40px; box-sizing: border-box; }
.msg { padding: 40px 0; text-align: center; color: $sub; font-size: 14px; &.small { padding: 10px 0 0; } }
.guest { padding: 40px 8px; text-align: center; img { width: 56px; height: 56px; } h2 { margin: 12px 0 0; font-size: 20px; } p { margin: 8px 0 18px; font-size: 14.5px; line-height: 1.6; color: $sub-ink; word-break: keep-all; } }
.btn { width: 100%; height: 50px; border: 0; border-radius: $radius; background: #5A3C08; color: #fff; font-size: 15.5px; font-weight: 700; }
.top { width: 100%; display: block; padding: 14px 16px; border: 0; border-radius: 14px; background: $honey-strip; text-align: left; color: inherit;
    .l { display: flex; align-items: center; gap: 6px; img { width: 24px; height: 24px; } b { font-size: 22px; color: $honey-ink; letter-spacing: -.5px; } em { margin-left: auto; font-style: normal; font-size: 13px; color: $amber-700; font-weight: 700; } }
    small { display: block; margin-top: 4px; font-size: 12.5px; color: #7A5A1E; }
    .bar { display: block; margin-top: 10px; height: 7px; border-radius: 4px; background: #FFEFC4; overflow: hidden; i { display: block; height: 100%; background: $honey-500; } }
}
.quiz { margin-top: 12px; padding: 14px 16px; border-radius: 14px; border: 1px solid $line;
    .k { margin: 0; font-size: 12.5px; font-weight: 800; color: $amber-700; }
    .q { margin: 4px 0 8px; font-size: 15.5px; font-weight: 700; line-height: 1.45; word-break: keep-all; }
    .o { width: 100%; display: flex; justify-content: space-between; align-items: center; min-height: 42px; margin-top: 6px; padding: 8px 12px; border: 1.5px solid transparent; border-radius: 10px; background: $band; color: $ink; font-size: 14px; text-align: left;
        i { font-style: normal; font-weight: 800; } &.right { border-color: $honey-500; background: $honey-50; } &.wrong { opacity: .6; } &:disabled { cursor: default; } }
    .retry { margin: 8px 0 0; font-size: 13px; color: $sub; }
}
.streak { margin-top: 12px; padding: 14px 12px 12px; border-radius: 14px; border: 1px solid $line;
    .t { display: flex; justify-content: space-between; margin: 0; padding: 0 4px; font-size: 13.5px; font-weight: 700; em { font-style: normal; color: $amber-700; } }
}
.hexes { display: flex; justify-content: space-between; align-items: center; margin-top: 10px; }
.hex { width: 40px; height: 44px; clip-path: polygon(50% 0, 100% 25%, 100% 75%, 50% 100%, 0 75%, 0 25%); background: $band; display: flex; align-items: center; justify-content: center; font-size: 11.5px; font-weight: 700; color: $sub-2;
    &.f { background: $honey-500; color: $honey-ink; } &.today { background: $honey-300; }
    &.big { width: 50px; height: 56px; background: $honey-100; color: $amber-700; font-size: 12px; &.f { background: $honey-500; color: $honey-ink; } }
}
.tasks { margin-top: 8px; }
.task { display: flex; align-items: center; gap: 12px; padding: 12px 0; border-bottom: 1px solid $line;
    .ic { width: 36px; height: 36px; flex: none; border-radius: 11px; background: $honey-100; display: flex; align-items: center; justify-content: center; font-size: 16px; color: $amber-700; font-weight: 800; }
    .tx { flex: 1; min-width: 0; b { display: block; font-size: 15px; } small { display: block; font-size: 12.5px; color: $sub; } }
}
.sm { flex: none; height: 34px; padding: 0 12px; border: 0; border-radius: 9px; background: #5A3C08; color: #fff; font-size: 13px; font-weight: 700;
    &.done { background: $band; color: $sub-2; cursor: default; } &:disabled:not(.done) { opacity: .5; } }
.foot { margin-top: 16px; font-size: 12px; line-height: 1.6; color: $sub; word-break: keep-all; }
</style>
