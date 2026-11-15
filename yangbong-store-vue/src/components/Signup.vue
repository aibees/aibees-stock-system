<template>
    <div id="signup">
        <BrandHeader title="회원가입" back="/login" />

        <main class="su-main">
            <form class="su-form" novalidate @submit.prevent="submit">

                <!-- 이메일 + 인증코드 -->
                <div class="su-field">
                    <label for="su-email">이메일</label>
                    <div class="su-inline">
                        <input id="su-email" v-model.trim="email" type="email" inputmode="email"
                            autocomplete="email" placeholder="example@email.com" :disabled="sending" @input="onEmailInput" />
                        <button type="button" class="btn-line" :disabled="!emailValid || sending || cooldown > 0" @click="sendCode">
                            {{ sending ? '보내는 중…' : (verifyToken ? (cooldown > 0 ? `재발송 ${cooldown}초` : '다시 받기') : '인증코드 받기') }}
                        </button>
                    </div>
                    <p v-if="email && !emailValid" class="su-err">이메일 주소를 확인해 주세요.</p>
                </div>

                <div v-if="verifyToken" class="su-field">
                    <label for="su-code">인증코드</label>
                    <div class="su-inline">
                        <input id="su-code" v-model.trim="code" type="text" inputmode="numeric" maxlength="6"
                            autocomplete="one-time-code" placeholder="메일로 받은 6자리" />
                        <span class="su-timer" :class="{ over: remain <= 0 }" aria-live="polite">{{ remainText }}</span>
                    </div>
                </div>

                <!-- 이름 -->
                <div class="su-field">
                    <label for="su-name">이름(닉네임)</label>
                    <input id="su-name" v-model.trim="userName" type="text" maxlength="45" autocomplete="nickname" />
                </div>

                <!-- 비밀번호 -->
                <div class="su-field">
                    <label for="su-pw">비밀번호</label>
                    <input id="su-pw" v-model="password" type="password" autocomplete="new-password"
                        placeholder="8자 이상, 대/소문자·숫자·특수문자 포함" />
                    <p v-if="password && !passwordStrong" class="su-err">8자 이상, 대문자·소문자·숫자·특수문자를 각 1자 이상 넣어 주세요.</p>
                </div>
                <div class="su-field">
                    <label for="su-pw2">비밀번호 확인</label>
                    <input id="su-pw2" v-model="password2" type="password" autocomplete="new-password" />
                    <p v-if="password2 && password2 !== password" class="su-err">비밀번호가 일치하지 않습니다.</p>
                </div>

                <ConsentChecklist v-model="agree" />

                <p v-if="errorMsg" class="su-error" role="alert">{{ errorMsg }}</p>

                <div class="su-actions">
                    <button type="submit" class="btn-primary" :disabled="!canSubmit || submitting">
                        {{ submitting ? '가입하는 중…' : '가입하기' }}
                    </button>
                    <button type="button" class="btn-ghost" :disabled="submitting" @click="router.replace('/login')">로그인으로</button>
                </div>
            </form>
        </main>
    </div>
</template>

<script setup>
/**
 * 이메일 회원가입(/signup).
 * ① POST /api/oauth/signup/code  — 이메일로 6자리 코드 발송, verifyToken 을 받는다(코드는 응답에 없다)
 * ② POST /api/oauth/signup       — 코드·이름·비밀번호·항목별 동의를 보내면 가입 후 바로 로그인 토큰을 준다
 * 이미 가입된 이메일(네이버 가입 포함)은 서버가 거절한다.
 */
import aibeesApi from '@scripts/aibeesApi.js';
import { assUserSession } from '@scripts/stores/user-stores';
import ConsentChecklist from './common/ConsentChecklist.vue';
import { PRIVACY_POLICY_VERSION } from '@scripts/privacyPolicy.js';
import { TERMS_VERSION } from '@scripts/termsOfService.js';

const router = useRouter();
const userSession = assUserSession();

const EMAIL_REGEX = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
// 비밀번호 재설정(Login.vue)과 같은 규칙. 서버도 같은 규칙으로 다시 검사한다.
const PASSWORD_REGEX = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,}$/;

const email = ref('');
const code = ref('');
const userName = ref('');
const password = ref('');
const password2 = ref('');
const agree = ref({ age14: false, terms: false, privacy: false });

const verifyToken = ref('');
const sending = ref(false);
const submitting = ref(false);
const errorMsg = ref('');

const emailValid = computed(() => EMAIL_REGEX.test(email.value));
const passwordStrong = computed(() => PASSWORD_REGEX.test(password.value));
const allAgreed = computed(() => agree.value.age14 && agree.value.terms && agree.value.privacy);
const canSubmit = computed(() =>
    !!verifyToken.value && /^\d{6}$/.test(code.value) && remain.value > 0
    && userName.value.length > 0 && passwordStrong.value && password.value === password2.value
    && allAgreed.value);

/* ── 코드 유효시간 / 재발송 대기 ── */
const expiresAt = ref(0);
const resendAt = ref(0);
const now = ref(Date.now());
let ticker = null;
onMounted(() => { ticker = setInterval(() => { now.value = Date.now(); }, 1000); });
onBeforeUnmount(() => clearInterval(ticker));

const remain = computed(() => Math.max(0, Math.round((expiresAt.value - now.value) / 1000)));
const remainText = computed(() => (remain.value > 0
    ? `${Math.floor(remain.value / 60)}:${String(remain.value % 60).padStart(2, '0')}`
    : '시간 초과'));
const cooldown = computed(() => Math.max(0, Math.round((resendAt.value - now.value) / 1000)));

// 이메일을 바꾸면 이전 이메일로 받은 인증은 무효
const onEmailInput = () => {
    if (verifyToken.value) {
        verifyToken.value = '';
        code.value = '';
    }
};

const apiError = (err, fallback) =>
    err?.response?.data?.error?.message ?? err?.error?.message ?? fallback;

const sendCode = async () => {
    if (!emailValid.value || sending.value) return;
    sending.value = true;
    errorMsg.value = '';
    try {
        const { data } = await aibeesApi.post('/api/oauth/signup/code', { email: email.value });
        if (!data?.success) throw { error: data?.error };
        verifyToken.value = data.data.verifyToken;
        expiresAt.value = Date.now() + data.data.expiresIn * 1000;
        resendAt.value = Date.now() + 60 * 1000;
        code.value = '';
    } catch (err) {
        errorMsg.value = apiError(err, '인증코드를 보내지 못했어요.');
    } finally {
        sending.value = false;
    }
};

const submit = async () => {
    if (!canSubmit.value || submitting.value) return;
    submitting.value = true;
    errorMsg.value = '';
    try {
        const { data } = await aibeesApi.post('/api/oauth/signup', {
            verifyToken: verifyToken.value,
            code: code.value,
            userName: userName.value,
            password: password.value,
            termsVersion: TERMS_VERSION,
            policyVersion: PRIVACY_POLICY_VERSION,
            agreeAge14: agree.value.age14,
            agreeTerms: agree.value.terms,
            agreePrivacy: agree.value.privacy,
        });
        if (!data?.success) throw { error: data?.error };
        userSession.loginUser(data.data, false);
        alert('가입을 환영합니다!');
        router.replace({ name: 'home' });
    } catch (err) {
        errorMsg.value = apiError(err, '가입을 완료하지 못했어요.');
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

#signup {
    min-height: 100vh;
    background: #fff;
    color: $ink;
    font-family: 'Pretendard', 'IBM Plex Sans KR', -apple-system, 'Apple SD Gothic Neo', sans-serif;
}

.su-main {
    max-width: 480px;
    margin: 0 auto;
    padding: 24px 20px 40px;
    text-align: left;           // 전역 #app 가운데 정렬을 끊는다
}

.su-form { display: flex; flex-direction: column; gap: 18px; }

.su-field {
    display: flex;
    flex-direction: column;
    gap: 6px;
    label { font-size: 13px; font-weight: 600; color: $sub; }
    input {
        width: 100%;
        min-height: 48px;
        padding: 0 12px;
        box-sizing: border-box;
        border: 1px solid $line;
        border-radius: 10px;
        background: #fff;
        color: $ink;
        font-size: 16px;   // iOS 확대 방지
        font-family: inherit;
        &:focus { outline: none; border-color: $brown; }
        &:disabled { background: #FAF6EA; }
    }
}

.su-inline {
    display: flex;
    align-items: center;
    gap: 8px;
    input { flex: 1; min-width: 0; }
}

.su-timer {
    flex-shrink: 0;
    min-width: 56px;
    text-align: right;
    font-size: 14px;
    font-weight: 600;
    color: $brown;
    font-variant-numeric: tabular-nums;
    &.over { color: #C0392B; }
}

.su-err { margin: 0; font-size: 12px; color: #C0392B; }
.su-error { margin: 0; font-size: 13px; color: #C0392B; }

.su-actions { display: flex; flex-direction: column; gap: 8px; }

.btn-line, .btn-primary, .btn-ghost {
    min-height: 48px;
    border-radius: 10px;
    font-size: 15px;
    font-weight: 600;
    font-family: inherit;
    cursor: pointer;
    &:focus-visible { outline: 2px solid $brown; outline-offset: 2px; }
    &:disabled { opacity: .45; cursor: default; }
}
.btn-line {
    flex-shrink: 0;
    padding: 0 14px;
    border: 1px solid $hero;
    background: #fff;
    color: $hero;
    font-size: 14px;
    white-space: nowrap;
}
.btn-primary { border: 0; background: $hero; color: $cream; }
.btn-ghost { border: 1px solid $line; background: #fff; color: $sub; }
</style>
