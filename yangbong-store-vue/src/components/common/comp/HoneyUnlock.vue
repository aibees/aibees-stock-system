<template>
    <!-- 프리미엄 잠금 화면 안: 꿀로 오늘 하루 열기. 로그인 전에는 로그인 안내 -->
    <div class="hu">
        <template v-if="!loggedIn">
            <button type="button" class="btn" @click="router.push('/login')">로그인하고 꿀로 열기</button>
        </template>
        <template v-else-if="honey.available">
            <div class="opt on"><div><b>오늘 하루 이용권</b><small>24시간 프리미엄 전체</small></div><span class="pr">{{ fmt(cost) }}꿀</span></div>
            <p class="mybal">내 꿀 <b>{{ fmt(honey.balance) }}꿀</b><template v-if="enough"> · 쓰고 나면 {{ fmt(honey.balance - cost) }}꿀</template></p>
            <button v-if="enough" type="button" class="btn" :disabled="honey.busy" @click="open">꿀 {{ fmt(cost) }}으로 오늘 하루 열기</button>
            <button v-else type="button" class="btn" @click="router.push(HONEY_PATH)">꿀 모으러 가기 ({{ fmt(cost - honey.balance) }}꿀 더 필요)</button>
            <button v-if="enough" type="button" class="link" @click="router.push(HONEY_PATH)">꿀 모으러 가기 ›</button>
            <p v-if="error" class="err" role="alert">{{ error }}</p>
        </template>
    </div>
</template>

<script setup>
import { useHoneyStore } from '@scripts/stores/honey-store.js';
import { assUserSession } from '@scripts/stores/user-stores.js';
import { HONEY_PATH } from '@scripts/support.js';

const emit = defineEmits(['opened']);
const router = useRouter();
const honey = useHoneyStore();
const loggedIn = computed(() => !!assUserSession().user.accessToken);
const cost = computed(() => honey.summary?.dayPass?.cost ?? 1000);
const enough = computed(() => honey.balance >= cost.value);
const error = ref('');
const fmt = (n) => Number(n ?? 0).toLocaleString();

const open = async () => {
    error.value = '';
    const r = await honey.buyDayPass();
    if (r === true) emit('opened');
    else error.value = r;
};
onMounted(() => { if (loggedIn.value) honey.load(); });
</script>

<style scoped lang="scss">
@use '@@/_home-tokens.scss' as *;

.hu { width: 100%; margin-top: 12px; }
.opt { display: flex; align-items: center; justify-content: space-between; padding: 13px 14px; border-radius: 12px; background: $card; border: 1.5px solid $honey-500; text-align: left;
    b { display: block; font-size: 15px; } small { font-size: 12.5px; color: $sub; } .pr { font-size: 15px; font-weight: 800; color: $honey-ink; } }
.mybal { margin: 12px 0 10px; font-size: 13px; color: $sub-ink; b { color: $honey-ink; } }
.btn { width: 100%; height: 50px; border: 0; border-radius: $radius; background: #5A3C08; color: #fff; font: inherit; font-size: 15.5px; font-weight: 700; cursor: pointer; &:disabled { opacity: .5; } }
.link { margin-top: 8px; border: 0; background: transparent; color: $amber-700; font: inherit; font-size: 14px; font-weight: 700; cursor: pointer; }
.err { margin: 8px 0 0; font-size: 13px; color: $up; }
</style>
