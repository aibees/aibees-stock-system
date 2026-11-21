<template>
    <div id="login" :aria-busy="isLoading.toString()">

        <!-- 화면 정중앙에 [타이틀 / (아이디 폼) / 로그인 버튼들 / 링크] 묶음을 둔다. 스크롤 없음(2026-11-21).
             '아이디로 로그인'을 누르면 가운데 칸이 열리면서 타이틀은 위로, 소셜 버튼은 아래로 밀린다. -->
        <!-- 뒤로가기: 아이디 폼이 열려 있으면 폼을 닫고, 아니면 이전 화면으로 -->
        <button type="button" class="lg-back" aria-label="뒤로가기" @click="goBack">
            <svg viewBox="0 0 24 24" width="24" height="24" aria-hidden="true">
                <path d="M15 5l-7 7 7 7" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
        </button>

        <main class="lg-stage">
            <header class="lg-head">
                <img class="lg-logo" src="/favicon.svg" alt="" aria-hidden="true" />
                <h1 class="lg-name">양봉상회</h1>
            </header>

            <!-- 가운데 칸: 아이디·비밀번호 폼 (열리면 높이 0 → 자동) -->
            <div class="lg-slot" :class="{ open: showIdLogin }" :inert="showIdLogin ? null : ''">
                <div class="lg-slot-inner">
                    <form class="lg-form" novalidate @submit.prevent="emaillogin">
                        <div class="lg-field">
                            <label for="lg-id">아이디</label>
                            <input id="lg-id" ref="idInputEl" v-model.trim="emailData.loginId" type="text" autocomplete="username"
                                autocapitalize="none" autocorrect="off" spellcheck="false" />
                            <p class="lg-hint">기존 회원은 가입한 이메일의 @ 앞부분이 아이디예요.</p>
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
                </div>
            </div>

            <!-- 로그인 버튼 중 가장 위: 아이디로 로그인 (폼이 열리면 접힌다) -->
            <div class="lg-slot" :class="{ open: !showIdLogin }" :inert="showIdLogin ? '' : null">
                <div class="lg-slot-inner">
                    <button type="button" class="btn-ghost lg-idbtn" :disabled="isLoading" @click="openIdLogin">
                        아이디로 로그인
                    </button>
                </div>
            </div>

            <div class="lg-or" aria-hidden="true"><span>또는</span></div>

            <!-- 소셜 로그인 -->
            <div class="lg-social">
                <!-- 구글 버튼은 GIS 가 그린다(구글 브랜드 가이드). 웹에서 클라이언트 ID 가 설정됐을 때만 보인다 -->
                <div v-show="googleReady" ref="googleBtnEl" class="lg-google"></div>

                <!-- Apple 로그인(iOS 앱만). Apple 디자인 가이드: 검은 바탕·흰 로고·다른 소셜 버튼과 같은 크기 -->
                <button v-if="showApple" type="button" class="btn-apple" :disabled="isLoading" @click="applelogin">
                    <svg class="apple-logo" viewBox="0 0 17 20" width="15" height="18" aria-hidden="true">
                        <path fill="currentColor" d="M14.1 10.6c0-2.6 2.1-3.8 2.2-3.9-1.2-1.8-3.1-2-3.7-2-1.6-.2-3.1.9-3.9.9-.8 0-2-.9-3.4-.9C3.5 4.8 1.8 5.8.9 7.4c-1.9 3.3-.5 8.1 1.3 10.8.9 1.3 1.9 2.7 3.3 2.7 1.3-.1 1.8-.9 3.4-.9s2 .9 3.4.8c1.4 0 2.3-1.3 3.2-2.6 1-1.5 1.4-2.9 1.4-3-.1 0-2.8-1.1-2.8-4.6zM11.5 3c.7-.9 1.2-2.1 1.1-3.3-1 0-2.3.7-3 1.6-.7.8-1.3 2-1.1 3.2 1.1.1 2.3-.6 3-1.5z"/>
                    </svg>
                    Apple로 계속하기
                </button>

                <button type="button" class="btn-naver" :disabled="isLoading" @click="naverlogin">
                    <span class="naver-n" aria-hidden="true">N</span>
                    네이버로 계속하기
                </button>
            </div>

            <p v-if="!showIdLogin && errorMsg" class="lg-error" role="alert">{{ errorMsg }}</p>

            <!-- 회원가입은 왼쪽, 아이디·비밀번호 찾기는 오른쪽 -->
            <nav class="lg-links" aria-label="계정">
                <router-link to="/signup" class="lg-link strong">회원가입</router-link>
                <span class="lg-links-right">
                    <router-link :to="{ path: '/find-account', query: { tab: 'id' } }" class="lg-link">아이디 찾기</router-link>
                    <span class="lg-sep" aria-hidden="true">·</span>
                    <router-link :to="{ path: '/find-account', query: { tab: 'pw' } }" class="lg-link">비밀번호 찾기</router-link>
                </span>
            </nav>
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
import { takeAfterLogin } from '@scripts/authPaths.js';
import aibeesApi from '../scripts/aibeesApi.js'
import * as StrUtils from '@/scripts/utils/stringUtils.js'
import { assUserSession } from '../scripts/stores/user-stores';
import { renderGoogleButton } from '@/scripts/googleLogin.js'
import { appleLoginAvailable, authorizeApple } from '@/scripts/appleLogin.js'

const userSession = assUserSession();
const router = useRouter()
const route = useRoute()
const isLoading = ref(false)
const isResetTarget = computed(() => route.query.status === 'reset')
const errorMsg = ref('')

// 아이디 입력란은 '아이디로 로그인'을 눌러야 보인다. 초기화 안내로 들어왔을 때는 바로 펼친다.
const showIdLogin = ref(isResetTarget.value)
const idInputEl = ref(null)
const openIdLogin = async () => {
    showIdLogin.value = true
    await nextTick()
    idInputEl.value?.focus()
}

const goBack = () => {
    // 초기화 안내로 들어온 경우가 아니면, 열린 아이디 폼부터 닫는다
    if (showIdLogin.value && !isResetTarget.value) {
        showIdLogin.value = false
        errorMsg.value = ''
        return
    }
    if (window.history.state?.back) router.back()
    else router.replace({ name: 'home' })
}

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
 * body: { loginId, new_password }
 * 성공 시 modal 닫고 재로그인 유도
 */
const submitReset = async () => {
    if (!canSubmitReset.value) return
    isResetting.value = true
    try {
        await aibeesApi.post('/api/oauth/password/reset', {
            loginId: emailData.loginId,
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

// 아이디 로그인(2026-11-20~). 저장 키는 savedLoginId — 예전 savedEmail 이 남아 있으면 그 값을 쓴다
// (서버가 '@' 가 있는 값은 이메일로 찾아 준다). 다음 로그인 때 savedLoginId 로 바뀐다.
const emailData = reactive({
    loginId: localStorage.getItem('rememberEmail') === 'true'
        ? (localStorage.getItem('savedLoginId') ?? localStorage.getItem('savedEmail') ?? '')
        : '',
    pswd: ''
});

// 체크 해제 시 저장된 ID도 즉시 제거
watch(rememberEmail, (val) => {
    localStorage.setItem('rememberEmail', val)
    if (!val) { localStorage.removeItem('savedLoginId'); localStorage.removeItem('savedEmail') }
})
watch(autoLogin, (val) => {
    localStorage.setItem('autoLogin', val)
    if (!val) localStorage.removeItem('userSession')
})
// ─────────────────────────────────────────────────────────────

const emaillogin = async () => {
    errorMsg.value = ''
    if (StrUtils.isEmpty(emailData.loginId) || StrUtils.isEmpty(emailData.pswd)) {
        errorMsg.value = '아이디와 비밀번호를 입력해 주세요.'
        return;
    }

    isLoading.value = true;

    try {
        const body = { loginId: emailData.loginId, pswd: emailData.pswd };
        const { data } = await aibeesApi.post('/api/oauth/email', body);
        if (data.success) {
            // 아이디 기억하기
            localStorage.removeItem('savedEmail')   // 예전 키 정리
            if (rememberEmail.value) {
                localStorage.setItem('savedLoginId', emailData.loginId)
            } else {
                localStorage.removeItem('savedLoginId')
            }
            userSession.loginUser(data.data, autoLogin.value);
            router.push(takeAfterLogin() || { name: 'home' });   // 보려던 화면이 있으면 그리로
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

// ── 구글 로그인 (웹) ───────────────────────────────────────────
const googleBtnEl = ref(null)
const googleReady = ref(false)

const onGoogleResponse = (res) => {
    if (res.consentRequired) {
        // 회원정보는 저장됨. 동의해야 로그인 토큰을 받는다(네이버와 같은 동의 화면).
        sessionStorage.setItem('socialConsent', JSON.stringify({
            provider: 'google',
            consentToken: res.consentToken,
            socialResult: res.socialResult,
            profile: res.profile,
        }))
        return router.replace({ name: 'signup-consent' })
    }
    userSession.loginUser(res, autoLogin.value)
    if (res.socialResult === 'linked') alert('기존 계정에 구글 로그인을 연결했어요.')
    else if (res.socialResult === 'created') alert('구글 계정으로 가입했어요. 환영합니다!')
    router.replace(takeAfterLogin() || { name: 'home' })
}

onMounted(async () => {
    googleReady.value = await renderGoogleButton(googleBtnEl.value, {
        onStart: () => { errorMsg.value = ''; isLoading.value = true },
        onResponse: (res) => { isLoading.value = false; onGoogleResponse(res) },
        onError: (msg) => { isLoading.value = false; errorMsg.value = msg },
    })
})
// ─────────────────────────────────────────────────────────────

// ── Apple 로그인 (iOS 앱) ──────────────────────────────────────
const showApple = appleLoginAvailable()

const applelogin = async () => {
    errorMsg.value = ''
    isLoading.value = true
    try {
        const apple = await authorizeApple()
        if (!apple) return   // 사용자가 취소
        const { data } = await aibeesApi.post('/api/oauth/apple', {
            identityToken: apple.identityToken,
            nonce: apple.nonce,
            givenName: apple.givenName,
            familyName: apple.familyName,
        })
        const res = data.data
        if (res.consentRequired) {
            sessionStorage.setItem('socialConsent', JSON.stringify({
                provider: 'apple',
                consentToken: res.consentToken,
                socialResult: res.socialResult,
                profile: res.profile,
            }))
            return router.replace({ name: 'signup-consent' })
        }
        userSession.loginUser(res, autoLogin.value)
        if (res.socialResult === 'linked') alert('기존 계정에 Apple 로그인을 연결했어요.')
        else if (res.socialResult === 'created') alert('Apple 계정으로 가입했어요. 환영합니다!')
        router.replace(takeAfterLogin() || { name: 'home' })
    } catch (err) {
        errorMsg.value = apiError(err, 'Apple 로그인에 실패했어요. 잠시 후 다시 시도해 주세요.')
    } finally {
        isLoading.value = false
    }
}
// ─────────────────────────────────────────────────────────────

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
    // 화면 전체 고정 — 어떤 크기에서도 스크롤이 생기지 않는다
    position: fixed;
    inset: 0;
    overflow: hidden;
    display: flex;
    align-items: center;      // 묶음 전체를 세로 정중앙에
    justify-content: center;
    background: #fff;
    color: $ink;
    text-align: left;
    font-family: 'Pretendard', 'IBM Plex Sans KR', -apple-system, 'Apple SD Gothic Neo', sans-serif;
}

.lg-back {
    position: absolute;
    z-index: 2;
    top: calc(env(safe-area-inset-top, 0px) + 32px);
    left: 8px;
    width: 44px;
    height: 44px;
    display: flex;
    align-items: center;
    justify-content: center;
    border: 0;
    border-radius: 50%;
    background: transparent;
    color: $brown-ink;
    cursor: pointer;
    &:focus-visible { outline: 2px solid $brown; outline-offset: 2px; }
}
@media (max-height: 560px) {
    .lg-back { top: calc(env(safe-area-inset-top, 0px) + 20px); }
}

.lg-stage {
    width: 100%;
    max-width: 400px;
    max-height: 100%;
    box-sizing: border-box;
    padding: env(safe-area-inset-top, 0px) 20px env(safe-area-inset-bottom, 0px);
    display: flex;
    flex-direction: column;
    gap: 12px;
}

/* ── 타이틀 ── */
/* 노란 지붕: 타이틀 뒤에서 화면 맨 위까지 이어지고, 아래 가장자리는 물결. 타이틀이 움직이면 같이 움직인다. */
.lg-head {
    position: relative;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
    padding-bottom: 16px;
    margin-bottom: 8px;
    &::before {
        content: '';
        position: absolute;
        z-index: -1;
        left: calc(50% - 50vw);
        width: 100vw;
        top: -100vh;
        bottom: 0;
        background: $bar;
    }
    &::after {
        content: '';
        position: absolute;
        z-index: -1;
        left: calc(50% - 50vw);
        width: 100vw;
        bottom: -8px;
        height: 8px;
        background: radial-gradient(circle at 50% 0, #{$bar} 6.5px, transparent 7px) repeat-x;
        background-size: 16px 8px;
    }
}
.lg-logo { width: 56px; height: 56px; }
.lg-name {
    margin: 0;
    font-family: 'Pretendard', sans-serif;
    font-size: 26px;
    font-weight: 700;
    color: $brown-ink;
    letter-spacing: .5px;
}

/* ── 접히고 펼쳐지는 칸(높이 0 ↔ 자동). 묶음이 정중앙이라 열리면 타이틀은 위로, 소셜은 아래로 밀린다 ── */
.lg-slot {
    display: grid;
    grid-template-rows: 0fr;
    margin-bottom: -12px;     // 접힌 상태에서 gap 이 남지 않게
    opacity: 0;
    visibility: hidden;
    transition: grid-template-rows .45s cubic-bezier(.2, .8, .2, 1), margin-bottom .45s cubic-bezier(.2, .8, .2, 1),
        opacity .3s ease, visibility 0s linear .45s;
    &.open {
        grid-template-rows: 1fr;
        margin-bottom: 0;
        opacity: 1;
        visibility: visible;
        transition: grid-template-rows .45s cubic-bezier(.2, .8, .2, 1), margin-bottom .45s cubic-bezier(.2, .8, .2, 1),
            opacity .35s ease .1s, visibility 0s;
    }
}
.lg-slot-inner { min-height: 0; overflow: hidden; padding: 2px; margin: -2px; }
.lg-idbtn { width: 100%; }

.lg-social { display: flex; flex-direction: column; gap: 10px; }

@media (prefers-reduced-motion: reduce) {
    .lg-slot, .lg-slot.open { transition: none; }
}
/* 키가 작은 화면: 장식·보조 문구를 줄여 스크롤 없이 들어가게 */
@media (max-height: 700px) {
    .lg-stage { gap: 8px; }
    .lg-slot { margin-bottom: -8px; }
    .lg-logo { width: 40px; height: 40px; }
    .lg-name { font-size: 22px; }
    .lg-head { padding-bottom: 4px; }
    .lg-hint { display: none; }
    .lg-form { gap: 8px; }
    .btn-primary, .btn-ghost, .btn-naver, .btn-apple { min-height: 44px; }
    .lg-link { min-height: 36px; }
}
@media (max-height: 560px) {
    .lg-logo { display: none; }
    .lg-check { min-height: 24px; }
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
.lg-hint { margin: 0; font-size: 12px; color: #8B7B6B; }

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

.lg-links {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    margin-top: 4px;
    font-size: 14px;
}
.lg-links-right { display: inline-flex; align-items: center; gap: 6px; }
.lg-link {
    display: inline-flex;
    align-items: center;
    min-height: 44px;
    color: $sub;
    text-decoration: none;
    &.strong { color: $brown; font-weight: 700; }
    &:focus-visible { outline: 2px solid $brown; outline-offset: 2px; border-radius: 4px; }
}
.lg-sep { color: #C9BBA6; }

/* ── 구글 버튼(GIS iframe) — 가운데 정렬, 높이는 다른 버튼과 비슷하게 ── */
.lg-google {
    display: flex;
    justify-content: center;
    min-height: 44px;
}

/* ── 버튼 ── */
.btn-primary, .btn-ghost, .btn-naver, .btn-apple {
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

.btn-apple {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    border: 0;
    background: #000;
    color: #fff;
    .apple-logo { margin-top: -2px; }
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
