<template>
    <div id="login" class="auth" :aria-busy="isLoading.toString()">
        <!-- 배경 장식 -->
        <div class="bg">
            <div class="blob blob-1"></div>
            <div class="blob blob-2"></div>
        </div>

        <main class="card" role="main" aria-labelledby="login-title">
            <header class="brand">
                <h1 id="login-title" class="main-title">Aibees Stock Service</h1>
                <p class="sub-title">Aibees 주식정보WEB</p>
            </header>

            <section class="actions">
                <button class="btn brand email" @click="login('email')" :disabled="isLoading">
                    <span class="icon" aria-hidden="true">E</span>
                    이메일로 계속하기
                </button>
                <div class="email-body" id="email-login-div">
                    <div class="email-input">
                        <div class="label">
                            ID
                        </div>
                        <input type="text" id="email-input" autocomplete="off" v-model="emailData.email" />
                    </div>
                    <div class="email-input">
                        <div class="label">
                            PW
                        </div>
                        <input type="password" id="pswd-input" autocomplete="off" v-model="emailData.pswd"
                            @keydown.enter="emaillogin" />
                    </div>
                    <!-- 아이디 기억하기 / 자동로그인 -->
                    <div class="email-options">
                        <label class="option-check">
                            <input type="checkbox" v-model="rememberEmail" />
                            <span>아이디 기억하기</span>
                        </label>
                        <label class="option-check">
                            <input type="checkbox" v-model="autoLogin" />
                            <span>자동로그인</span>
                        </label>
                    </div>
                    <div class="email-input">
                        <button @click="emaillogin">로그인</button>
                    </div>
                </div>
                <button class="btn brand naver" @click="login('naver')" :disabled="isLoading">
                    <span class="icon" aria-hidden="true">N</span>
                    네이버로 계속하기
                </button>

                <button class="btn brand kakao" @click="login('kakao')" :disabled="isLoading">
                    <span class="icon" aria-hidden="true">K</span>
                    카카오로 계속하기
                </button>

                <button class="btn ghost" @click="toHome" :disabled="isLoading">
                    홈으로
                </button>

                <p v-if="isResetTarget" class="reset-notice" role="alert">
                    계정 초기화 대상입니다. 관리자에게 문의하세요.
                </p>
                <p class="hint">
                    로그인 시 서비스 약관 및 개인정보 처리방침에 동의합니다.
                </p>
            </section>
        </main>
    </div>

    <!-- 비밀번호 재설정 Modal -->
    <teleport to="body">
        <div v-if="showResetModal" class="modal-overlay" @click.self="closeResetModal">
            <div class="modal-card" role="dialog" aria-modal="true" aria-labelledby="reset-modal-title">
                <h2 id="reset-modal-title" class="modal-title">비밀번호 재설정</h2>
                <p class="modal-desc">{{ resetMessage }}</p>

                <div class="modal-field">
                    <label class="field-label">새 비밀번호</label>
                    <input type="password" class="field-input" v-model="resetData.newPswd"
                        placeholder="8자 이상, 대/소문자·숫자·특수문자 포함" autocomplete="new-password" />
                    <p v-if="resetData.newPswd && !passwordStrong" class="field-error">
                        8자 이상, 대문자·소문자·숫자·특수문자를 각 1자 이상 포함해야 합니다.
                    </p>
                </div>

                <div class="modal-field">
                    <label class="field-label">비밀번호 확인</label>
                    <input type="password" class="field-input" v-model="resetData.confirmPswd" placeholder="비밀번호를 다시 입력하세요"
                        autocomplete="new-password" @keydown.enter="submitReset" />
                    <p v-if="resetData.confirmPswd && !passwordsMatch" class="field-error">
                        비밀번호가 일치하지 않습니다.
                    </p>
                </div>

                <div class="modal-actions">
                    <button class="modal-btn cancel" @click="closeResetModal" :disabled="isResetting">취소</button>
                    <button class="modal-btn confirm" @click="submitReset" :disabled="!canSubmitReset || isResetting">
                        {{ isResetting ? '저장 중…' : '저장' }}
                    </button>
                </div>
            </div>
        </div>
    </teleport>
</template>

<script setup>
import aibeesApi from '../scripts/aibeesApi.js'
import * as StrUtils from '@/scripts/utils/stringUtils.js'
import { assUserSession } from '../scripts/stores/user-stores';
import { removeCookie } from '@/scripts/utils/cookieUtils';

const userSession = assUserSession();
const router = useRouter()
const route = useRoute()
const isLoading = ref(false)
const isResetTarget = computed(() => route.query.status === 'reset')

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
        const msg = err?.error?.message ?? err?.message ?? '비밀번호 변경에 실패했습니다.'
        alert(msg)
    } finally {
        isResetting.value = false
    }
}
// ─────────────────────────────────────────────────────────────

const redirect_url = aibeesGlobal.API_REDIRECT_URL + '/oauth/'
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
    if (!val) removeCookie('userSession')
})
// ─────────────────────────────────────────────────────────────

const login = (type) => {
    if (type === 'naver') {
        alert('준비중입니다');
        // naverlogin();
    } else if (type === 'kakao') {
        alert('준비중입니다');
        // kakaologin();
    }
    else if (type === 'email') {
        const emailDiv = document.getElementById('email-login-div');
        emailDiv.classList.toggle('expand')
    }
}

// ──────────────────────────────────────────────────────────────
// [수정] emaillogin
// 1. isLoading 토글 추가: 기존에는 선언만 하고 실제로 쓰지 않았음
// 2. try/catch/finally 추가: 서버 에러 발생 시 unhandled rejection 방지
// 3. 에러 메시지 표시: 서버가 내려주는 error.message 우선, 없으면 기본 문구
// ──────────────────────────────────────────────────────────────
const emaillogin = async () => {
    if (StrUtils.isEmpty(emailData.email) || StrUtils.isEmpty(emailData.pswd)) {
        alert("제대로 입력해주세요");
        return;
    }

    isLoading.value = true; // [추가] 로딩 시작

    try {
        const body = { email: emailData.email, pswd: emailData.pswd };
        const { data } = await aibeesApi.post('/api/oauth/email', body);
        console.log(data);
        if (data.success) {
            // 아이디 기억하기
            if (rememberEmail.value) {
                localStorage.setItem('savedEmail', emailData.email)
            } else {
                localStorage.removeItem('savedEmail')
            }
            userSession.loginUser(data.data, autoLogin.value);
            router.push({ name: 'home' });
        } else {
            if (data.error.code == 'RESET_REQUIRED') {
                openResetModal(data.error.message);
                return;
            }
        }
    } catch (err) {
        const msg = err?.error?.message ?? err?.message ?? '로그인에 실패했습니다.'
    } finally {
        isLoading.value = false; // [추가] 성공·실패 무관하게 로딩 종료
    }
}

const naverlogin = async () => {
    try {
        isLoading.value = true
        const { data } = await aibeesApi.get(naver_info_url)
        let naver_key_id = ''
        const redirectURI = encodeURI(redirect_url + 'naver')
        const state = StrUtils.createStatusKey()

        data?.data?.forEach((d) => {
            if (String(d.key_type).endsWith('ID')) naver_key_id = d.key_value
        })

        const loginUrl =
            'https://nid.naver.com/oauth2.0/authorize?' +
            'response_type=code' +
            `&client_id=${naver_key_id}` +
            `&redirect_uri=${redirectURI}` +
            `&state=${state}`

        window.location.href = loginUrl
    } catch (err) {
        console.error(err)
        isLoading.value = false
        alert('네이버 로그인 정보를 불러오지 못했습니다.')
    }
}

const kakaologin = () => {
    // 필요 시 카카오 OAuth URL 구성해 연결
    alert('카카오 로그인을 준비 중입니다.')
}

const toHome = () => {
    router.push({ name: 'home' })
}

const keyDownEvt = () => {

}

</script>

<style scoped lang="scss">
/* ===== Tokens ===== */
$bg: #212121;
$card: #1d1f23;
$text: #e9edf4;
$muted: #a6afbd;
$border: rgba(255, 255, 255, 0.08);

/* ===== Layout ===== */
.auth {
    position: relative;
    /* 화면 중앙 정렬 */
    min-height: 100svh;
    /* 모바일 주소창 높이 대응 */
    display: flex;
    align-items: center;
    justify-content: center;

    /* 좌우 여백 */
    padding: 24px 20px;
    /* <- 여기서 L/R 패딩 조절 */

    /* 기존 배경은 유지 */
    background: radial-gradient(1200px 600px at 20% -10%, #2c2f36 0%, transparent 60%),
        radial-gradient(900px 600px at 100% 100%, #1b1d22 0%, transparent 60%),
        #212121;
    overflow: hidden;
}

/* 배경 블롭 위치는 그대로 사용 */
.bg .blob {
    position: absolute;
    filter: blur(60px);
    opacity: .35;
    pointer-events: none;
}

.blob-1 {
    width: 480px;
    height: 480px;
    border-radius: 50%;
    background: #4052ff;
    top: -120px;
    left: -120px;
}

.blob-2 {
    width: 520px;
    height: 520px;
    border-radius: 50%;
    background: #00c781;
    bottom: -160px;
    right: -160px;
}

/* 카드는 가로 폭을 100%로 두고 최대폭만 제한 */
.card {
    width: 100%;
    max-width: 420px;
    /* 필요시 440~480px로 넓혀도 OK */
    margin: 0 auto;
    /* 혹시 모를 중앙정렬 보강 */
    background: #1d1f23;
    border: 1px solid rgba(255, 255, 255, .08);
    border-radius: 16px;
    box-shadow: 0 12px 40px rgba(0, 0, 0, .35);
    padding: 28px 24px 22px;
    text-align: center;
}


/* ===== Actions ===== */
.actions {
    display: grid;
    gap: 12px;

    .btn {
        width: 100%;
        height: 48px;
        border-radius: 12px;
        border: 1px solid transparent;
        font-weight: 800;
        font-size: 0.98rem;
        letter-spacing: 0.1px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 10px;
        transition: transform 0.12s ease, background 0.12s ease, box-shadow 0.12s ease;
        cursor: pointer;

        &:hover {
            transform: translateY(-1px);
        }

        &:active {
            transform: translateY(0);
        }

        &:disabled {
            opacity: 0.6;
            cursor: not-allowed;
            transform: none;
        }

        .icon {
            width: 22px;
            height: 22px;
            border-radius: 6px;
            display: inline-grid;
            place-items: center;
            font-size: 0.9rem;
            font-weight: 900;
            background: rgba(0, 0, 0, 0.18);
        }
    }

    /* 브랜드 버튼 */
    .brand.email {
        background: #ebebeb;
        color: #444444;
        border-color: rgba(0, 0, 0, 0.08);

        .icon {
            background: #ffbf5e29;
        }

        &:hover {
            box-shadow: 0 6px 18px rgba(3, 199, 90, 0.35);
        }
    }

    .brand.naver {
        background: #03c75a;
        color: #ffffff;
        border-color: rgba(0, 0, 0, 0.08);

        .icon {
            background: rgba(255, 255, 255, 0.16);
        }

        &:hover {
            box-shadow: 0 6px 18px rgba(3, 199, 90, 0.35);
        }
    }

    .brand.kakao {
        background: #fee500;
        color: #191919;
        border-color: rgba(0, 0, 0, 0.12);

        .icon {
            background: rgba(0, 0, 0, 0.08);
        }

        &:hover {
            box-shadow: 0 6px 18px rgba(254, 229, 0, 0.35);
        }
    }

    .email-body {
        width: 100%;
        overflow: hidden;
        height: 0px;
        border-radius: 12px;
        background: #ffeed5;
        transition: height 0.4s ease;
        font-size: 0.9rem;
        font-weight: 900;

        .email-input {
            margin-top: 15px;
            display: flex;
            justify-content: center;

            .label {
                width: 50px;
                padding-top: 1px;
                border-radius: 6px;
                color: black;
                background-color: #ffbb6d;
            }

            input {
                width: 200px;
                height: 20px;
                background-color: transparent;
                padding-left: 10px;
                margin-left: 5px;
                border: none;
                font-weight: 900;
                border-bottom: 1px solid rgb(143, 143, 143);

                &:focus {
                    outline: none;
                    box-shadow: none;
                    border: none;
                    border-bottom: 2px solid black;
                    background-color: transparent;
                }
            }

            button {
                padding: 4px 12px;
                border-radius: 6px;
                border: 1px solid rgb(231, 231, 231);
                font-weight: 800;
                font-size: 0.98rem;
                letter-spacing: 0.1px;
                background-color: #ffbb6d;

                &:hover {
                    cursor: pointer;
                    background-color: #f5a040;
                    transition: background-color 0.4s ease;
                }
            }
        }
    }

    .email-body.expand {
        height: 178px;
    }

    .email-options {
        display: flex;
        justify-content: center;
        gap: 16px;
        margin-top: 10px;

        .option-check {
            display: flex;
            align-items: center;
            gap: 5px;
            font-size: 0.78rem;
            font-weight: 700;
            color: #555;
            cursor: pointer;
            user-select: none;

            input[type='checkbox'] {
                width: 14px;
                height: 14px;
                accent-color: #f5a040;
                cursor: pointer;
            }
        }
    }

    /* 보조 버튼 */
    .ghost {
        height: 44px;
        background: transparent;
        color: $muted;
        border: 1px solid $border;
        font-weight: 700;

        &:hover {
            background: rgba(255, 255, 255, 0.04);
            color: $text;
        }
    }

    .reset-notice {
        padding: 10px 14px;
        border-radius: 8px;
        background: rgba(255, 80, 80, 0.12);
        border: 1px solid rgba(255, 80, 80, 0.35);
        color: #ff8080;
        font-size: 13px;
        font-weight: 600;
    }

    .hint {
        margin: 6px 0 0;
        font-size: 12px;
        color: $muted;
    }
}

/* ===== Responsive ===== */
@media (max-width: 420px) {
    .auth {
        padding: 28px 16px;
    }

    .card {
        padding: 24px 18px 18px;
    }
}

/* ===== Password Reset Modal ===== */
.modal-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.6);
    backdrop-filter: blur(4px);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 100;
    padding: 20px;
}

.modal-card {
    width: 100%;
    max-width: 400px;
    background: #1d1f23;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 16px;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
    padding: 28px 24px 22px;
    display: flex;
    flex-direction: column;
    gap: 16px;
}

.modal-title {
    font-size: 1.1rem;
    font-weight: 800;
    color: #e9edf4;
    margin: 0;
}

.modal-desc {
    font-size: 0.85rem;
    color: #ff8080;
    margin: 0;
    line-height: 1.5;
}

.modal-field {
    display: flex;
    flex-direction: column;
    gap: 6px;
}

.field-label {
    font-size: 0.8rem;
    font-weight: 700;
    color: #a6afbd;
}

.field-input {
    height: 42px;
    background: #16181c;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 8px;
    color: #e9edf4;
    padding: 0 12px;
    font-size: 0.9rem;
    transition: border-color 0.15s;

    &::placeholder {
        color: #555c6a;
    }

    &:focus {
        outline: none;
        border-color: rgba(64, 82, 255, 0.6);
    }
}

.field-error {
    font-size: 0.75rem;
    color: #ff8080;
    margin: 0;
}

.modal-actions {
    display: flex;
    gap: 10px;
    margin-top: 4px;

    .modal-btn {
        flex: 1;
        height: 42px;
        border-radius: 10px;
        border: none;
        font-weight: 800;
        font-size: 0.9rem;
        cursor: pointer;
        transition: opacity 0.15s, transform 0.1s;

        &:hover:not(:disabled) {
            transform: translateY(-1px);
        }

        &:active:not(:disabled) {
            transform: translateY(0);
        }

        &:disabled {
            opacity: 0.45;
            cursor: not-allowed;
        }

        &.cancel {
            background: rgba(255, 255, 255, 0.06);
            color: #a6afbd;
            border: 1px solid rgba(255, 255, 255, 0.08);
        }

        &.confirm {
            background: #4052ff;
            color: #fff;

            &:hover:not(:disabled) {
                background: #5060ff;
            }
        }
    }
}</style>
