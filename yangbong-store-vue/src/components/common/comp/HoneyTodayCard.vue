<template>
    <!-- 홈 '오늘의 꿀' 카드. 로그인 전에는 로그인 안내, 꿀을 다 모은 날에는 '오늘 꿀을 다 모았어요' -->
    <div class="htc">
        <template v-if="!loggedIn">
            <div class="top"><img src="/img/emoji/honey.png" alt="" /><div class="tx"><b>꿀을 모아 프리미엄을 열어 보세요</b><small>로그인하면 출석·수업·광고로 꿀이 쌓여요</small></div>
                <button type="button" class="btn" @click="router.push('/login')">로그인</button></div>
        </template>
        <template v-else-if="honey.available">
            <div class="top"><img src="/img/emoji/honey.png" alt="" />
                <div class="tx">
                    <b>{{ honey.allDone ? '오늘 꿀을 다 모았어요' : `오늘 꿀 ${honey.todayEarned} 모았어요` }}</b>
                    <small>{{ honey.allDone ? `내 꿀 ${fmt(honey.balance)}` : `${fmt(honey.todayLeft)}꿀 더 모을 수 있어요` }}</small>
                </div>
                <button type="button" class="btn" @click="router.push(HONEY_PATH)">모으기</button></div>
            <div class="bar"><i :style="{ width: pct + '%' }"></i></div>
            <div v-if="!honey.allDone" class="chips">
                <span :class="{ done: s.attend.done }">출석 체크{{ s.attend.done ? '' : ` +${s.attend.amount}` }}</span>
                <span v-if="honey.adSupported" :class="{ done: s.ad.count >= s.ad.max }">광고 {{ s.ad.max - s.ad.count }}번</span>
                <span :class="{ done: s.quiz.done }">오늘의 문제{{ s.quiz.done ? '' : ` +${s.quiz.amount}` }}</span>
                <span v-if="s.lesson.done < s.lesson.total">수업 +{{ s.lesson.amount }}</span>
            </div>
        </template>
    </div>
</template>

<script setup>
import { useHoneyStore } from '@scripts/stores/honey-store.js';
import { assUserSession } from '@scripts/stores/user-stores.js';
import { HONEY_PATH } from '@scripts/support.js';

const router = useRouter();
const honey = useHoneyStore();
const loggedIn = computed(() => !!assUserSession().user.accessToken);
const s = computed(() => honey.summary);
const pct = computed(() => Math.min(100, Math.round((honey.todayEarned / (honey.todayTarget || 1)) * 100)));
const fmt = (n) => Number(n ?? 0).toLocaleString();
onMounted(() => { if (loggedIn.value) honey.load(); });
</script>

<style scoped lang="scss">
@use '@@/_home-tokens.scss' as *;

.htc { padding: 16px; border-radius: $radius; background: $honey-strip; border: 1px solid #FFEBC2; text-align: left; }
.top { display: flex; align-items: center; gap: 12px;
    img { width: 38px; height: 38px; flex: none; }
    .tx { flex: 1; min-width: 0; b { display: block; font-size: 16px; color: $honey-ink; letter-spacing: -.3px; } small { display: block; margin-top: 2px; font-size: 13px; color: #7A5A1E; } }
}
.btn { flex: none; height: 36px; padding: 0 13px; border: 0; border-radius: 9px; background: #5A3C08; color: #fff; font: inherit; font-size: 13.5px; font-weight: 700; cursor: pointer; }
.bar { margin-top: 12px; height: 6px; border-radius: 3px; background: #FFE9B3; overflow: hidden; i { display: block; height: 100%; background: $honey-500; } }
.chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 12px;
    span { display: inline-flex; align-items: center; height: 28px; padding: 0 10px; border-radius: 14px; background: $card; font-size: 12.5px; font-weight: 600; color: $honey-ink; }
    span.done { color: $sub-2; text-decoration: line-through; font-weight: 500; }
}
</style>
