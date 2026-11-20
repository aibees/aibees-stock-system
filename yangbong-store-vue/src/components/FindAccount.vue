<template>
    <div id="find-account">
        <BrandHeader title="아이디·비밀번호 찾기" back="/login" />

        <main class="fa-main">
            <div class="fa-tabs" role="tablist">
                <button v-for="t in TABS" :key="t.key" type="button" role="tab" class="fa-tab"
                    :class="{ on: tab === t.key }" :aria-selected="tab === t.key" @click="switchTab(t.key)">
                    {{ t.label }}
                </button>
            </div>

            <!-- ── 1) 이메일 → 인증코드 받기 (두 탭 공통, 코드는 탭마다 따로 발급) ── -->
            <form class="fa-form" novalidate @submit.prevent>
                <div class="fa-field">
                    <label for="fa-email">가입한 이메일</label>
                    <div class="fa-inline">
                        <input id="fa-email" v-model.trim="email" type="email" inputmode="email" autocomplete="email"
                            placeholder="example@email.com" :disabled="sending || done" @input="onEmailInput" />
                        <button type="button" class="btn-line" :disabled="!emailValid || sending || cooldown > 0 || done" @click="sendCode">
                            {{ sending ? '보내는 중…' : (verifyToken ? (cooldown > 0 ? `재발송 ${cooldown}초` : '다시 받기') : '인증코드 받기') }}
                        </button>
                    </div>
                    <p v-if="email && !emailValid" class="fa-err">이메일 주소를 확인해 주세요.</p>
                    <p v-else-if="verifyToken && !done" class="fa-help">
                        가입된 이메일이면 인증코드를 보냈어요. 메일이 오지 않으면 네이버·구글·Apple 로 가입했는지 확인해 주세요.
                    </p>
                </div>

                <!-- ── 2-a) 아이디 찾기: 코드 확인 → 아이디(앞뒤 2자만) ── -->
                <template v-if="tab === 'id' && verifyToken">
                    <div v-if="!done" class="fa-field">
                        <label for="fa-code">인증코드</label>
                        <div class="fa-inline">
                            <input id="fa-code" v-model.trim="code" type="text" inputmode="numeric" maxlength="6"
                                autocomplete="one-time-code" placeholder="메일로 받은 6자리" @keydown.enter.prevent="findId" />
                            <span class="fa-timer" :class="{ over: remain <= 0 }" aria-live="polite">{{ remainText }}</span>
                            <button type="button" class="btn-line" :disabled="!codeValid || remain <= 0 || working" @click="findId">
                                {{ working ? '확인 중…' : '확인' }}
                            </button>
                        </div>
                    </div>

                    <section v-else class="fa-result" aria-live="polite">
                        <p class="fa-result-label">가입된 아이디</p>
                        <p v-for="id in foundIds" :key="id" class="fa-result-id">{{ id }}</p>
                        <p class="fa-help">개인정보 보호를 위해 아이디 가운데는 *로 가렸어요.</p>
                        <div class="fa-actions">
                            <button type="button" class="btn-primary" @click="router.replace('/login')">로그인하러 가기</button>
                            <button type="button" class="btn-ghost" @click="switchTab('pw')">비밀번호 찾기</button>
                        </div>
                    </section>
                </template>

                <!-- ── 2-b) 비밀번호 재설정: 코드 + 아이디 + 새 비밀번호 ── -->
                <template v-if="tab === 'pw' && verifyToken">
                    <div class="fa-field">
                        <label for="fa-code">인증코드</label>
                        <div class="fa-inline">
                            <input id="fa-code" v-model.trim="code" type="text" inputmode="numeric" maxlength="6"
                                autocomplete="one-time-code" placeholder="메일로 받은 6자리" />
                            <span class="fa-timer" :class="{ over: remain <= 0 }" aria-live="polite">{{ remainText }}</span>
                        </div>
                    </div>
                    <div class="fa-field">
                        <label for="fa-id">아이디</label>
                        <input id="fa-id" v-model.trim="loginId" type="text" maxlength="20" autocomplete="username"
                            autocapitalize="none" autocorrect="off" spellcheck="false" />
                    </div>
                    <div class="fa-field">
                        <label for="fa-pw">새 비밀번호</label>
                        <input id="fa-pw" v-model="password" type="password" autocomplete="new-password"
                            placeholder="8자 이상, 대/소문자·숫자·특수문자 포함" />
                        <p v-if="password && !passwordStrong" class="fa-err">8자 이상, 대문자·소문자·숫자·특수문자를 각 1자 이상 넣어 주세요.</p>
                    </div>
                    <div class="fa-field">
                        <label for="fa-pw2">새 비밀번호 확인</label>
                        <input id="fa-pw2" v-model="password2" type="password" autocomplete="new-password" />
                        <p v-if="password2 && password2 !== password" class="fa-err">비밀번호가 일치하지 않습니다.</p>
                    </div>
                    <button type="button" class="btn-primary" :disabled="!canReset || working" @click="resetPassword">
                        {{ working ? '바꾸는 중…' : '비밀번호 바꾸기' }}
                    </button>
                </template>

                <p v-if="errorMsg" class="fa-error" role="alert">{{ errorMsg }}</p>
            </form>
        </main>
    </div>
</template>

<script setup>
/**
 * 아이디 찾기 · 비밀번호 재설정(/find-account?tab=id|pw). 비로그인 화면(authPaths.AUTH_PATHS).
 * 아이디 찾기 : POST /api/oauth/find-id/code → /find-id/verify        → 아이디(앞뒤 2자만 보임)
 * 비밀번호    : POST /api/oauth/password/code → /password/reset-by-code(코드·아이디·새 비밀번호)
 * 두 탭의 코드는 서로 다르다(서버가 용도를 토큰에 담아 구분). 탭을 바꾸면 받은 코드는 버린다.
 */
import aibeesApi from '@scripts/aibeesApi.js';

const router = useRouter();
const route = useRoute();

const TABS = [{ key: 'id', label: '아이디 찾기' }, { key: 'pw', label: '비밀번호 찾기' }];
const API = {
    id: { code: '/api/oauth/find-id/code' },
    pw: { code: '/api/oauth/password/code' },
};
const EMAIL_REGEX = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
const PASSWORD_REGEX = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,}$/;   // 서버와 같은 규칙

const tab = ref(route.query.tab === 'pw' ? 'pw' : 'id');
const email = ref('');
const code = ref('');
const loginId = ref('');
const password = ref('');
const password2 = ref('');
const verifyToken = ref('');
const foundIds = ref([]);
const sending = ref(false);
const working = ref(false);
const errorMsg = ref('');

const emailValid = computed(() => EMAIL_REGEX.test(email.value));
const codeValid = computed(() => /^\d{6}$/.test(code.value));
const passwordStrong = computed(() => PASSWORD_REGEX.test(password.value));
const done = computed(() => tab.value === 'id' && foundIds.value.length > 0);
const canReset = computed(() => codeValid.value && remain.value > 0 && loginId.value.length > 0
    && passwordStrong.value && password.value === password2.value);

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

const apiError = (err, fallback) => err?.response?.data?.error?.message ?? err?.error?.message ?? fallback;

const resetState = () => {
    verifyToken.value = '';
    code.value = '';
    password.value = '';
    password2.value = '';
    foundIds.value = [];
    errorMsg.value = '';
    expiresAt.value = 0;
    resendAt.value = 0;
};

const switchTab = (key) => {
    if (tab.value === key) return;
    tab.value = key;
    resetState();
    router.replace({ query: { tab: key } });
};

// 이메일을 바꾸면 이전 이메일로 받은 코드는 무효
const onEmailInput = () => { if (verifyToken.value) resetState(); };

const post = async (url, body) => {
    const { data } = await aibeesApi.post(url, body);
    if (!data?.success) throw { error: data?.error };
    return data.data;
};

const sendCode = async () => {
    if (!emailValid.value || sending.value) return;
    sending.value = true;
    errorMsg.value = '';
    try {
        const res = await post(API[tab.value].code, { email: email.value });
        verifyToken.value = res.verifyToken;
        expiresAt.value = Date.now() + res.expiresIn * 1000;
        resendAt.value = Date.now() + 60 * 1000;
        code.value = '';
    } catch (err) {
        errorMsg.value = apiError(err, '인증코드를 보내지 못했어요.');
    } finally {
        sending.value = false;
    }
};

const findId = async () => {
    if (!codeValid.value || remain.value <= 0 || working.value) return;
    working.value = true;
    errorMsg.value = '';
    try {
        const res = await post('/api/oauth/find-id/verify', { verifyToken: verifyToken.value, code: code.value });
        foundIds.value = res.maskedLoginIds || [];
    } catch (err) {
        errorMsg.value = apiError(err, '아이디를 찾지 못했어요.');
    } finally {
        working.value = false;
    }
};

const resetPassword = async () => {
    if (!canReset.value || working.value) return;
    working.value = true;
    errorMsg.value = '';
    try {
        await post('/api/oauth/password/reset-by-code', {
            verifyToken: verifyToken.value, code: code.value,
            loginId: loginId.value.toLowerCase(), newPassword: password.value,
        });
        alert('비밀번호를 바꿨어요. 새 비밀번호로 로그인해 주세요.');
        router.replace('/login');
    } catch (err) {
        errorMsg.value = apiError(err, '비밀번호를 바꾸지 못했어요.');
    } finally {
        working.value = false;
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

#find-account {
    min-height: 100vh;
    background: #fff;
    color: $ink;
    font-family: 'Pretendard', 'IBM Plex Sans KR', -apple-system, 'Apple SD Gothic Neo', sans-serif;
}

.fa-main {
    max-width: 480px;
    margin: 0 auto;
    padding: 12px 20px 40px;
    text-align: left;
}

/* 탭: 글자 + 밑줄(뱃지·알약 모양 쓰지 않음) */
.fa-tabs {
    display: flex;
    border-bottom: 1px solid $line;
    margin-bottom: 20px;
}
.fa-tab {
    flex: 1;
    min-height: 48px;
    border: 0;
    border-bottom: 2px solid transparent;
    margin-bottom: -1px;
    background: none;
    color: $sub;
    font: inherit;
    font-size: 15px;
    cursor: pointer;
    &.on { color: $brown; font-weight: 700; border-bottom-color: $brown; }
    &:focus-visible { outline: 2px solid $brown; outline-offset: -2px; }
}

.fa-form { display: flex; flex-direction: column; gap: 18px; }

.fa-field {
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

.fa-inline {
    display: flex;
    align-items: center;
    gap: 8px;
    input { flex: 1; min-width: 0; }
}

.fa-timer {
    flex-shrink: 0;
    min-width: 44px;
    text-align: right;
    font-size: 14px;
    font-weight: 600;
    color: $brown;
    font-variant-numeric: tabular-nums;
    &.over { color: #C0392B; }
}

.fa-err { margin: 0; font-size: 12px; color: #C0392B; }
.fa-error { margin: 0; font-size: 13px; color: #C0392B; }
.fa-help { margin: 0; font-size: 12px; line-height: 1.5; color: $sub; word-break: keep-all; }

.fa-result {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 4px 0 0;
}
.fa-result-label { margin: 0; font-size: 13px; font-weight: 600; color: $sub; }
.fa-result-id {
    margin: 0;
    padding: 4px 0;
    font-size: 22px;
    font-weight: 700;
    letter-spacing: 1px;
    color: $ink;
    font-variant-numeric: tabular-nums;
}
.fa-actions { display: flex; flex-direction: column; gap: 8px; margin-top: 8px; }

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
