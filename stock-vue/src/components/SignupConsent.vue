<template>
    <div id="signup-consent">
        <BrandHeader title="회원가입" />

        <main class="sc-main">
            <template v-if="!pending">
                <p class="sc-title">가입 정보를 찾을 수 없어요</p>
                <p class="sc-msg">네이버로 다시 로그인해 주세요.</p>
                <button type="button" class="btn-primary" @click="toLogin">로그인 화면으로</button>
            </template>

            <template v-else>
                <section class="sc-section">
                    <h2 class="sc-title">거의 다 됐어요</h2>
                    <p class="sc-msg">서비스를 이용하려면 아래 항목에 동의해 주세요.</p>
                    <dl class="sc-profile">
                        <div><dt>이름</dt><dd>{{ pending.profile?.user_name || '-' }}</dd></div>
                        <div><dt>이메일</dt><dd>{{ pending.profile?.email || '-' }}</dd></div>
                    </dl>
                </section>

                <ConsentChecklist v-model="agree" />

                <p v-if="errorMsg" class="sc-error" role="alert">{{ errorMsg }}</p>

                <div class="sc-actions">
                    <button type="button" class="btn-primary" :disabled="!allAgreed || submitting" @click="submit">
                        {{ submitting ? '처리 중…' : '동의하고 시작하기' }}
                    </button>
                    <button type="button" class="btn-ghost" :disabled="submitting" @click="cancel">취소</button>
                </div>
            </template>
        </main>
    </div>
</template>

<script setup>
/**
 * 네이버 가입 — 가입 동의 화면(/oauth/naver/consent). 만 14세·이용약관·개인정보 수집·이용을 항목별로 받는다.
 * NaverCallback 이 서버 응답 consentRequired 를 받으면 consentToken 을 sessionStorage('naverConsent')에
 * 담아 이리로 보낸다(회원정보는 이미 저장됨). 동의하면 POST /api/oauth/naver/consent 가 동의 기록 후
 * 토큰을 주고, 로그인 처리 뒤 홈으로 간다. 취소하면 로그인하지 않는다 — 다음 네이버 로그인 때 다시 묻는다.
 */
import aibeesApi from '@scripts/aibeesApi.js';
import { assUserSession } from '@scripts/stores/user-stores';
import ConsentChecklist from './common/ConsentChecklist.vue';
import { PRIVACY_POLICY_VERSION } from '@scripts/privacyPolicy.js';
import { TERMS_VERSION } from '@scripts/termsOfService.js';

const router = useRouter();
const userSession = assUserSession();

const readPending = () => {
    try {
        return JSON.parse(sessionStorage.getItem('naverConsent') || 'null');
    } catch {
        return null;
    }
};

const pending = ref(readPending());
const agree = ref({ age14: false, terms: false, privacy: false });
const allAgreed = computed(() => agree.value.age14 && agree.value.terms && agree.value.privacy);
const submitting = ref(false);
const errorMsg = ref('');

const toLogin = () => router.replace('/login');

const cancel = () => {
    sessionStorage.removeItem('naverConsent');
    toLogin();
};

const submit = async () => {
    if (!allAgreed.value || submitting.value) return;
    submitting.value = true;
    errorMsg.value = '';
    try {
        const { data } = await aibeesApi.post('/api/oauth/naver/consent', {
            consentToken: pending.value.consentToken,
            termsVersion: TERMS_VERSION,
            policyVersion: PRIVACY_POLICY_VERSION,
            agreeAge14: true,
            agreeTerms: true,
            agreePrivacy: true,
        });
        if (!data?.success) throw { error: data?.error };

        sessionStorage.removeItem('naverConsent');
        userSession.loginUser(data.data, localStorage.getItem('autoLogin') === 'true');
        if (data.data.naverResult === 'created') alert('네이버 계정으로 가입했어요. 환영합니다!');
        else if (data.data.naverResult === 'linked') alert('기존 계정에 네이버 로그인을 연결했어요.');
        router.replace({ name: 'home' });
    } catch (err) {
        errorMsg.value = err?.response?.data?.error?.message ?? err?.error?.message ?? '가입을 완료하지 못했어요.';
        submitting.value = false;
    }
};
</script>

<style scoped lang="scss">
$hero:  #74462A;
$brown: #7A4423;
$ink:   #2B1D14;
$sub:   #6B5B4E;
$line:  #EFE2BC;
$cream: #FFF8E1;

#signup-consent {
    min-height: 100vh;
    background: #fff;
    color: $ink;
    font-family: 'Pretendard', 'IBM Plex Sans KR', -apple-system, 'Apple SD Gothic Neo', sans-serif;
}

.sc-main {
    max-width: 480px;
    margin: 0 auto;
    padding: 32px 20px 40px;
    display: flex;
    flex-direction: column;
    gap: 20px;
    text-align: left;
}

.sc-section { display: flex; flex-direction: column; gap: 10px; }
.sc-title { margin: 0; font-size: 20px; font-weight: 700; }
.sc-msg { margin: 0; font-size: 14px; line-height: 1.6; color: $sub; word-break: keep-all; }

.sc-profile {
    margin: 0;
    border-top: 1px solid $line;
    > div {
        display: flex;
        gap: 12px;
        padding: 10px 0;
        border-bottom: 1px solid $line;
        font-size: 14px;
        line-height: 1.55;
    }
    dt { flex: 0 0 96px; color: $sub; }
    dd { margin: 0; flex: 1; min-width: 0; white-space: pre-line; word-break: keep-all; overflow-wrap: anywhere; }
}

.sc-error { margin: 0; font-size: 13px; color: #C0392B; }

.sc-actions { display: flex; flex-direction: column; gap: 8px; }

.btn-primary, .btn-ghost {
    min-height: 48px;
    padding: 0 22px;
    border-radius: 10px;
    font-size: 15px;
    font-weight: 600;
    font-family: inherit;
    cursor: pointer;
    &:focus-visible { outline: 2px solid $brown; outline-offset: 2px; }
    &:disabled { opacity: .45; cursor: default; }
}
.btn-primary { border: 0; background: $hero; color: $cream; }
.btn-ghost { border: 1px solid $line; background: #fff; color: $sub; }
</style>
