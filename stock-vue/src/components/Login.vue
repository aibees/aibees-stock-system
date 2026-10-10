<template>
    <div id="login" :aria-busy="isLoading.toString()">

        <!-- 상단: 홈과 같은 크림 띠 + 물결 가장자리, 가운데 브랜드 -->
        <header class="lg-head">
            <img class="lg-logo" src="/favicon.svg" alt="" aria-hidden="true" />
            <h1 class="lg-name">양봉상회</h1>
            <div class="lg-edge" aria-hidden="true"></div>
        </header>

        <main class="lg-main">
            <form class="lg-form" novalidate @submit.prevent="emaillogin">
                <div class="lg-field">
                    <label for="lg-email">이메일</label>
                    <input id="lg-email" v-model.trim="emailData.email" type="email" inputmode="email"
                        autocomplete="username" />
                </div>
                <div class="lg-field">
                    <label for="lg-pw">비밀번호</label>
                    <input id="lg-pw" v-model="emailData.pswd" type="password" autocomplete="current-password" />
                </div>

                <div class="lg-options">
                    <label class="lg-check">
                        <input type="checkbox" v-model="rememberEmail" />
                        <span>아이디 기억하기</span>
                    </label>
                    <label class="lg-check">
                        <input type="checkbox" v-model="autoLogin" />
                        <span>자동로그인</span>
                    </label>
                </div>

                <p v-if="isResetTarget" class="lg-error" role="alert">계정 초기화 대상입니다. 관리자에게 문의하세요.</p>
                <p v-if="errorMsg" class="lg-error" role="alert">{{ errorMsg }}</p>

                <button type="submit" class="btn-primary" :disabled="isLoading">
                    {{ isLoading ? '로그인 중…' : '로그인' }}
                </button>
            </form>

            <div class="lg-or" aria-hidden="true"><span>또는</span></div>

            <button type="button" class="btn-naver" :disabled="isLoading" @click="naverlogin">
                <span class="naver-n" aria-hidden="true">N</span>
                네이버로 계속하기
            </button>

            <p class="lg-signup">
                처음이신가요? <router-link to="/signup">이메일로 회원가입</router-link>
            </p>
        </main>

        <!-- 비밀번호 재설정 Modal -->
        <teleport to="body">
            <div v-if="showResetModal" class="lg-modal-overlay" @click.self="closeResetModal">
                <div class="lg-modal" role="dialog" aria-modal="true" aria-labelledby="reset-modal-title">
                    <h2 id="reset-modal-title" class="lg-modal-title">비밀번호 재설정</h2>
                    <p class="lg-modal-desc">{{ resetMessage }}</p>

                    <div class="lg-field">
                        <label for="lg-new-pw">새 비밀번호</label>
                        <input id="lg-new-pw" type="password" v-model="resetData.newPswd"
                            placeholder="8자 이상, 대/소문자·숫자·특수문자 포함" autocomplete="new-password" />
                        <p v-if="resetData.newPswd && !passwordStrong" class="lg-field-err">
                            8자 이상, 대문자·소문자·숫자·특수문자를 각 1자 이상 포함해야 합니다.
                        </p>
                    </div>

                    <div class="lg-field">
                        <label for="lg-new-pw2">비밀번호 확인</label>
                        <input id="lg-new-pw2" type="password" v-model="resetData.confirmPswd"
                            autocomplete="new-password" @keydown.enter="submitReset" />
                        <p v-if="resetData.confirmPswd && !passwordsMatch" class="lg-field-err">
                            비밀번호가 일치하지 않습니다.
                        </p>
                    </div>

                    <div class="lg-modal-actions">
                        <button type="button" class="btn-ghost" @click="closeResetModal" :disabled="isResetting">취소</button>
                        <button type="button" class="btn-primary" @click="submitReset" :disabled="!canSubmitReset || isResetting">
                            {{ isResetting ? '저장 중…' : '저장' }}
                        </button>
                    </div>
                </div>
            </div>
        </teleport>
    </div>
</template>

<script setup>
import aibeesApi from '../scripts/aibeesApi.js'
import * as StrUtils from '@/scripts/utils/stringUtils.js'
import { assUserSession } from '../scripts/stores/user-stores';

const userSession = assUserSession();
const router = useRouter()
const route = useRoute()
const isLoading = ref(false)
const isResetTarget = computed(() => route.query.status === 'reset')
const errorMsg = ref('')

const apiError = (err, fallback) =>
    err?.response?.data?.error?.message ?? err?.error?.message ?? fallback

// ── 비밀번호 재설정 Modal ──────────────────────────────────────
const showResetModal = ref(false)
const isResetting = ref(false)
const resetMessage = ref('')
const resetData = reactive({ newPswd: '', confirmPswd: '' })

// 보안 규율: 8자 이상, 대문자·소문자·숫자·특수문자 각 1자 이상
const PASSWORD_REGEX = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*()\-_=+\[\]{};:'",.<>/?\\|`~]).{8,}$/

const passwordStrong = computed(() => PASSWORD_REGEX.test(resetData.newPswd))
const passwordsMatch = computed(() => resetData.newPswd === resetData.confirmPswd)
const canSubmitReset = computed(() => passwordStrong.value && passwordsMatch.value && resetData.confirmPswd.length > 0)

const openResetModal = (message) => {
    resetMessage.value = message
    resetData.newPswd = ''
    resetData.confirmPswd = ''
    showResetModal.value = true
}

const closeResetModal = () => {
    showResetModal.value = false
}

/**
 * POST /api/oauth/password/reset
 * body: { email, new_password }
 * 성공 시 modal 닫고 재로그인 유도
 */
const submitReset = async () => {
    if (!canSubmitReset.value) return
    isResetting.value = true
    try {
        await aibeesApi.post('/api/oauth/password/reset', {
            email: emailData.email,
            new_password: resetData.newPswd
        })
        closeResetModal()
        alert('비밀번호가 변경되었습니다. 다시 로그인해주세요.')
    } catch (err) {
        alert(apiError(err, '비밀번호 변경에 실패했습니다.'))
    } finally {
        isResetting.value = false
    }
}
// ─────────────────────────────────────────────────────────────

// 네이버 콜백은 지금 열린 웹 주소 기준(개발/운영 모두 별도 설정 없이 맞는다).
// 네이버 개발자센터의 Callback URL 에 <origin>/oauth/naver 를 등록해야 한다.
const naver_callback_url = `${window.location.origin}/oauth/naver`
const naver_info_url = '/api/oauth/infos/naver'

// ── 아이디 기억하기 / 자동로그인 ───────────────────────────────
const rememberEmail = ref(localStorage.getItem('rememberEmail') === 'true')
const autoLogin     = ref(localStorage.getItem('autoLogin')     === 'true')

const emailData = reactive({
    email: localStorage.getItem('rememberEmail') === 'true'
        ? (localStorage.getItem('savedEmail') ?? '')
        : '',
    pswd: ''
});

// 체크 해제 시 저장된 ID도 즉시 제거
watch(rememberEmail, (val) => {
    localStorage.setItem('rememberEmail', val)
    if (!val) localStorage.removeItem('savedEmail')
})
watch(autoLogin, (val) => {
    localStorage.setItem('autoLogin', val)
    if (!val) localStorage.removeItem('userSession')
})
// ─────────────────────────────────────────────────────────────

const emaillogin = async () => {
    errorMsg.value = ''
    if (StrUtils.isEmpty(emailData.email) || StrUtils.isEmpty(emailData.pswd)) {
        errorMsg.value = '이메일과 비밀번호를 입력해 주세요.'
        return;
    }

    isLoading.value = true;

    try {
        const body = { email: emailData.email, pswd: emailData.pswd };
        const { data } = await aibeesApi.post('/api/oauth/email', body);
        if (data.success) {
            // 아이디 기억하기
            if (rememberEmail.value) {
                localStorage.setItem('savedEmail', emailData.email)
            } else {
                localStorage.removeItem('savedEmail')
            }
            userSession.loginUser(data.data, autoLogin.value);
            router.push({ name: 'home' });
        } else if (data.error?.code == 'RESET_REQUIRED') {
            openResetModal(data.error.message);
        } else {
            errorMsg.value = data.error?.message ?? '로그인에 실패했습니다.'
        }
    } catch (err) {
        errorMsg.value = apiError(err, '로그인에 실패했습니다.')
    } finally {
        isLoading.value = false;
    }
}

const naverlogin = async () => {
    try {
        isLoading.value = true
        const { data } = await aibeesApi.get(naver_info_url)
        let naver_key_id = ''
        const redirectURI = encodeURIComponent(naver_callback_url)
        // state 는 URL 에서 변형되지 않는 16진수 난수로 만든다. (예전 createStatusKey 는 AES Base64 라
        // '+' 가 섞이고, 콜백에서 Vue Router 가 '+' 를 공백으로 바꿔 state 비교가 실패했다)
        const state = Array.from(crypto.getRandomValues(new Uint8Array(16)), b => b.toString(16).padStart(2, '0')).join('')
        // 콜백에서 같은 state 인지 확인한다(다른 곳에서 만든 인가 응답으로 로그인되는 것 방지)
        sessionStorage.setItem('naverState', state)

        data?.data?.forEach((d) => {
            if (String(d.key_type).endsWith('ID')) naver_key_id = d.key_value
        })

        if (!naver_key_id) throw new Error('NAVER_AUTH_ID 없음')

        const loginUrl =
            'https://nid.naver.com/oauth2.0/authorize?' +
            'response_type=code' +
            `&client_id=${naver_key_id}` +
            `&redirect_uri=${redirectURI}` +
            `&state=${encodeURIComponent(state)}`

        window.location.href = loginUrl
    } catch (err) {
        console.error(err)
        isLoading.value = false
        alert('네이버 로그인 정보를 불러오지 못했습니다.')
    }
}
</script>

<style scoped lang="scss">
// 양봉상회 디자인 토큰(Home.vue 와 같은 값)
$bar:       #FFF6D2;
$line:      #EFE2BC;
$brown:     #7A4423;
$brown-ink: #5C3118;
$hero:      #74462A;
$ink:       #2B1D14;
$sub:       #6B5B4E;
$cream:     #FFF8E1;
$naver:     #03C75A;   // 네이버 로그인 버튼 가이드 색

#login {
    min-height: 100vh;
    min-height: 100svh;
    background: #fff;
    color: $ink;
    text-align: left;
    font-family: 'Pretendard', 'IBM Plex Sans KR', -apple-system, 'Apple SD Gothic Neo', sans-serif;
}

/* ── 상단 브랜드 띠 ── */
.lg-head {
    position: relative;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
    padding: calc(env(safe-area-inset-top, 0px) + 48px) 20px 28px;
    background: $bar;
}
.lg-logo { width: 64px; height: 64px; }
.lg-name {
    margin: 0;
    font-family: 'Do Hyeon', 'Pretendard', sans-serif;
    font-size: 34px;
    font-weight: 400;
    color: $brown-ink;
    letter-spacing: .5px;
}
// 홈 헤더와 같은 물결 가장자리
.lg-edge {
    position: absolute;
    left: 0;
    right: 0;
    bottom: -8px;
    height: 8px;
    background: radial-gradient(circle at 50% 0, #{$bar} 6.5px, transparent 7px) repeat-x;
    background-size: 16px 8px;
}

/* ── 본문 ── */
.lg-main {
    max-width: 400px;
    margin: 0 auto;
    padding: 36px 20px 40px;
    display: flex;
    flex-direction: column;
    gap: 16px;
}

.lg-form { display: flex; flex-direction: column; gap: 14px; }

.lg-field {
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
    }
}
.lg-field-err { margin: 0; font-size: 12px; color: #C0392B; }

.lg-options { display: flex; gap: 18px; }
.lg-check {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    min-height: 32px;
    font-size: 14px;
    color: $sub;
    cursor: pointer;
    input { width: 18px; height: 18px; margin: 0; accent-color: $hero; }
}

.lg-error { margin: 0; font-size: 13px; color: #C0392B; }

.lg-or {
    display: flex;
    align-items: center;
    gap: 12px;
    font-size: 12px;
    color: $sub;
    &::before, &::after { content: ''; flex: 1; height: 1px; background: $line; }
}

.lg-signup {
    margin: 4px 0 0;
    text-align: center;
    font-size: 14px;
    color: $sub;
    a { color: $brown; font-weight: 700; text-decoration: underline; }
}

/* ── 버튼 ── */
.btn-primary, .btn-ghost, .btn-naver {
    min-height: 50px;
    padding: 0 20px;
    border-radius: 10px;
    font-size: 16px;
    font-weight: 700;
    font-family: inherit;
    cursor: pointer;
    &:focus-visible { outline: 2px solid $brown; outline-offset: 2px; }
    &:disabled { opacity: .45; cursor: default; }
}
.btn-primary { border: 0; background: $hero; color: $cream; }
.btn-ghost { border: 1px solid $line; background: #fff; color: $sub; }
.btn-naver {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    border: 0;
    background: $naver;
    color: #fff;
    .naver-n { font-size: 18px; font-weight: 900; }
}

/* ── 비밀번호 재설정 모달 ── */
.lg-modal-overlay {
    position: fixed;
    inset: 0;
    z-index: 3000;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 20px;
    background: rgba(43, 29, 20, .45);
}
.lg-modal {
    width: 100%;
    max-width: 380px;
    padding: 22px 20px 18px;
    border-radius: 14px;
    background: #fff;
    color: $ink;
    text-align: left;
    display: flex;
    flex-direction: column;
    gap: 14px;
    font-family: 'Pretendard', 'IBM Plex Sans KR', -apple-system, 'Apple SD Gothic Neo', sans-serif;
}
.lg-modal-title { margin: 0; font-size: 18px; font-weight: 700; }
.lg-modal-desc { margin: 0; font-size: 14px; line-height: 1.5; color: $sub; }
.lg-modal-actions {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
    margin-top: 4px;
}
</style>
