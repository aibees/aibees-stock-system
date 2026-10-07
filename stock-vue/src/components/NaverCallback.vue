<template>
    <div id="naver-callback">
        <BrandHeader title="네이버 로그인" />

        <main class="nc-main" aria-live="polite">
            <template v-if="state === 'loading'">
                <div class="spinner" aria-hidden="true"></div>
                <p class="nc-msg">네이버 계정을 확인하고 있어요…</p>
            </template>

            <template v-else-if="state === 'error'">
                <p class="nc-title">로그인하지 못했어요</p>
                <p class="nc-msg">{{ message }}</p>
                <button type="button" class="btn-primary" @click="router.replace('/login')">로그인 화면으로</button>
            </template>
        </main>
    </div>
</template>

<script setup>
/**
 * 네이버 로그인 콜백(/oauth/naver).
 * 네이버가 붙여 보낸 code/state 를 서버(POST /api/oauth/naver)로 넘기면, 서버가 네이버에서 사용자 정보를
 * 직접 받아 ① 이미 연결된 계정이면 로그인 ② 이메일이 같은 기존 계정이면 연결 후 로그인
 * ③ 없으면 신규 가입(STOCK_USER) 후 로그인한다. 응답 형식은 이메일 로그인과 같다.
 * state 는 로그인 화면에서 만든 값과 같아야 한다(다른 곳에서 만든 인가 응답 재사용 방지).
 */
import aibeesApi from '@scripts/aibeesApi.js';
import { assUserSession } from '@scripts/stores/user-stores';

const route = useRoute();
const router = useRouter();
const userSession = assUserSession();

const state = ref('loading');
const message = ref('');

const fail = (msg) => {
    state.value = 'error';
    message.value = msg;
};

onMounted(async () => {
    const { code, state: returnedState, error, error_description: errorDesc } = route.query;
    const savedState = sessionStorage.getItem('naverState');
    sessionStorage.removeItem('naverState');   // 한 번만 쓴다

    if (error) {
        // 사용자가 동의 화면에서 취소한 경우 등
        return fail(error === 'access_denied' ? '네이버 로그인을 취소했어요.' : String(errorDesc || '네이버 인증에 실패했어요.'));
    }
    if (!code || !returnedState || returnedState !== savedState) {
        return fail('로그인 요청이 올바르지 않아요. 로그인 화면에서 다시 시도해 주세요.');
    }

    try {
        const { data } = await aibeesApi.post('/api/oauth/naver', { code, state: returnedState });
        if (!data?.success) return fail(data?.error?.message ?? '네이버 로그인에 실패했어요.');

        userSession.loginUser(data.data, localStorage.getItem('autoLogin') === 'true');
        if (data.data.naverResult === 'linked') alert('기존 계정에 네이버 로그인을 연결했어요.');
        else if (data.data.naverResult === 'created') alert('네이버 계정으로 가입했어요. 환영합니다!');
        router.replace({ name: 'home' });
    } catch (err) {
        fail(err?.response?.data?.error?.message ?? err?.error?.message ?? '네이버 로그인에 실패했어요.');
    }
});
</script>

<style scoped lang="scss">
$hero:  #74462A;
$brown: #7A4423;
$ink:   #2B1D14;
$sub:   #6B5B4E;
$line:  #EFE2BC;
$cream: #FFF8E1;

#naver-callback {
    min-height: 100vh;
    background: #fff;
    color: $ink;
    font-family: 'Pretendard', 'IBM Plex Sans KR', -apple-system, 'Apple SD Gothic Neo', sans-serif;
}

.nc-main {
    max-width: 420px;
    margin: 0 auto;
    padding: 96px 24px 48px;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 14px;
    text-align: center;
}
.nc-title { margin: 0; font-size: 18px; font-weight: 700; }
.nc-msg { margin: 0; font-size: 14px; line-height: 1.6; color: $sub; word-break: keep-all; }

.spinner {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    border: 3px solid $line;
    border-top-color: $hero;
    animation: spin .8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
@media (prefers-reduced-motion: reduce) { .spinner { animation-duration: 2.4s; } }

.btn-primary {
    margin-top: 8px;
    min-height: 46px;
    padding: 0 22px;
    border: 0;
    border-radius: 10px;
    background: $hero;
    color: $cream;
    font-size: 15px;
    font-weight: 600;
    font-family: inherit;
    cursor: pointer;
    &:focus-visible { outline: 2px solid $brown; outline-offset: 2px; }
}
</style>
