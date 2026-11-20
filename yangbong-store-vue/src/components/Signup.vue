<template>
    <div id="signup">
        <BrandHeader title="회원가입" back="/login" />

        <main class="su-main">
            <form class="su-form" novalidate @submit.prevent="submit">

                <!-- 아이디 + 중복 확인 -->
                <div class="su-field">
                    <label for="su-id">아이디</label>
                    <div class="su-inline">
                        <input id="su-id" v-model.trim="loginId" type="text" maxlength="20" autocomplete="username"
                            autocapitalize="none" autocorrect="off" spellcheck="false"
                            placeholder="영문 소문자·숫자 4~20자" @input="onLoginIdInput" />
                        <button type="button" class="btn-line" :disabled="!loginIdValid || checkingId || idChecked" @click="checkLoginId">
                            {{ checkingId ? '확인 중…' : (idChecked ? '확인 완료' : '중복 확인') }}
                        </button>
                    </div>
                    <p v-if="loginId && !loginIdValid" class="su-err">4~20자 영문 소문자·숫자로 쓰고, . _ - 를 섞을 수 있어요(첫 글자는 영문·숫자).</p>
                    <p v-else-if="idChecked" class="su-ok" aria-live="polite">✓ 사용할 수 있는 아이디예요.</p>
                    <p v-else-if="idMessage" class="su-err" aria-live="polite">{{ idMessage }}</p>
                </div>

                <!-- 이메일 + 인증코드(받기 → 확인) -->
                <div class="su-field">
                    <label for="su-email">이메일</label>
                    <div class="su-inline">
                        <input id="su-email" v-model.trim="email" type="email" inputmode="email"
                            autocomplete="email" placeholder="example@email.com" :disabled="sending || emailVerified" @input="onEmailInput" />
                        <button v-if="!emailVerified" type="button" class="btn-line" :disabled="!emailValid || sending || cooldown > 0" @click="sendCode">
                            {{ sending ? '보내는 중…' : (verifyToken ? (cooldown > 0 ? `재발송 ${cooldown}초` : '다시 받기') : '인증코드 받기') }}
                        </button>
                        <button v-else type="button" class="btn-line" :disabled="submitting" @click="resetEmail">변경</button>
                    </div>
                    <p v-if="email && !emailValid" class="su-err">이메일 주소를 확인해 주세요.</p>
                    <p v-else-if="emailVerified" class="su-ok">✓ 이메일 인증을 마쳤어요.</p>
                    <p v-else-if="verifyToken" class="su-help">메일로 받은 6자리 인증코드를 입력하고 확인을 눌러 주세요.</p>
                </div>

                <div v-if="verifyToken && !emailVerified" class="su-field">
                    <label for="su-code">인증코드</label>
                    <div class="su-inline">
                        <input id="su-code" v-model.trim="code" type="text" inputmode="numeric" maxlength="6"
                            autocomplete="one-time-code" placeholder="메일로 받은 6자리" @keydown.enter.prevent="verifyCode" />
                        <span class="su-timer" :class="{ over: remain <= 0 }" aria-live="polite">{{ remainText }}</span>
                        <button type="button" class="btn-line" :disabled="!/^\d{6}$/.test(code) || remain <= 0 || verifying" @click="verifyCode">
                            {{ verifying ? '확인 중…' : '확인' }}
                        </button>
                    </div>
                    <p v-if="codeError" class="su-err" role="alert">{{ codeError }}</p>
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
 * 회원가입(/signup). 로그인은 아이디로, 이메일은 인증·연락용으로 따로 받는다(2026-11-20).
 * ① POST /api/oauth/signup/login-id/check — 아이디 중복 확인
 * ② POST /api/oauth/signup/code          — 이메일로 6자리 코드 발송, verifyToken 을 받는다(코드는 응답에 없다)
 * ③ POST /api/oauth/signup/code/verify   — 코드 확인, verifiedToken 을 받는다(30분 유효)
 * ④ POST /api/oauth/signup               — verifiedToken·아이디·이름·비밀번호·항목별 동의 → 가입 후 바로 로그인
 * 이미 가입된 이메일(소셜 가입 포함)·이미 있는 아이디는 서버가 다시 거절한다.
 */
import aibeesApi from '@scripts/aibeesApi.js';
import { assUserSession } from '@scripts/stores/user-stores';
import ConsentChecklist from './common/ConsentChecklist.vue';
import { PRIVACY_POLICY_VERSION } from '@scripts/privacyPolicy.js';
import { TERMS_VERSION } from '@scripts/termsOfService.js';

const router = useRouter();
const userSession = assUserSession();

const EMAIL_REGEX = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
// 서버 LOGIN_ID_REGEX 와 같다(web_shared/auth/service.py). 대문자는 소문자로 바꿔 검사한다.
const LOGIN_ID_REGEX = /^[a-z0-9][a-z0-9._-]{3,19}$/;
// 비밀번호 재설정(Login.vue)과 같은 규칙. 서버도 같은 규칙으로 다시 검사한다.
const PASSWORD_REGEX = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,}$/;

const loginId = ref('');
const email = ref('');
const code = ref('');
const userName = ref('');
const password = ref('');
const password2 = ref('');
const agree = ref({ age14: false, terms: false, privacy: false });

const verifyToken = ref('');
const verifiedToken = ref('');
const verifying = ref(false);
const codeError = ref('');
const checkingId = ref(false);
const checkedId = ref('');     // 중복 확인을 통과한 아이디(소문자). 입력이 바뀌면 다시 확인해야 한다
const idMessage = ref('');
const sending = ref(false);
const submitting = ref(false);
const errorMsg = ref('');

const emailValid = computed(() => EMAIL_REGEX.test(email.value));
const normalizedId = computed(() => loginId.value.toLowerCase());
const loginIdValid = computed(() => LOGIN_ID_REGEX.test(normalizedId.value));
const idChecked = computed(() => !!checkedId.value && checkedId.value === normalizedId.value);
const emailVerified = computed(() => !!verifiedToken.value);
const passwordStrong = computed(() => PASSWORD_REGEX.test(password.value));
const allAgreed = computed(() => agree.value.age14 && agree.value.terms && agree.value.privacy);
const canSubmit = computed(() =>
    idChecked.value && emailVerified.value
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
        codeError.value = '';
    }
};
const resetEmail = () => {
    verifiedToken.value = '';
    verifyToken.value = '';
    code.value = '';
    codeError.value = '';
};

const onLoginIdInput = () => {
    if (!idChecked.value) idMessage.value = '';
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

const checkLoginId = async () => {
    if (!loginIdValid.value || checkingId.value) return;
    checkingId.value = true;
    idMessage.value = '';
    const target = normalizedId.value;
    try {
        const { data } = await aibeesApi.post('/api/oauth/signup/login-id/check', { loginId: target });
        if (!data?.success) throw { error: data?.error };
        if (normalizedId.value !== target) return;   // 확인하는 사이 입력이 바뀜
        checkedId.value = data.data.available ? data.data.loginId : '';
        idMessage.value = data.data.message;
    } catch (err) {
        checkedId.value = '';
        idMessage.value = apiError(err, '아이디를 확인하지 못했어요.');
    } finally {
        checkingId.value = false;
    }
};

const verifyCode = async () => {
    if (!/^\d{6}$/.test(code.value) || remain.value <= 0 || verifying.value) return;
    verifying.value = true;
    codeError.value = '';
    try {
        const { data } = await aibeesApi.post('/api/oauth/signup/code/verify', {
            verifyToken: verifyToken.value, code: code.value,
        });
        if (!data?.success) throw { error: data?.error };
        verifiedToken.value = data.data.verifiedToken;
    } catch (err) {
        codeError.value = apiError(err, '인증코드를 확인하지 못했어요.');
    } finally {
        verifying.value = false;
    }
};

const submit = async () => {
    if (!canSubmit.value || submitting.value) return;
    submitting.value = true;
    errorMsg.value = '';
    try {
        const { data } = await aibeesApi.post('/api/oauth/signup', {
            verifiedToken: verifiedToken.value,
            loginId: normalizedId.value,
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
.su-ok { margin: 0; font-size: 12px; color: #1E7A46; }
.su-help { margin: 0; font-size: 12px; color: $sub; }
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
