<template>
    <div id="user-option">
        <Headers :prop_title="title" />

        <div class="contents">

            <!-- ── 상단 타이틀 ── -->
            <section class="head-desc">
                <h2>개인설정</h2>
                <p class="sub-text">내 정보와 연동 키, 알림 설정을 변경할 수 있습니다. 변경한 항목만 저장됩니다.</p>
            </section>

            <div v-if="isLoading" class="loader-rows">
                <div v-for="n in 4" :key="n" class="skeleton-row"></div>
            </div>

            <form v-else class="setting-form" @submit.prevent="save">

                <!-- ════════════ 기본 정보 (user_master) ════════════ -->
                <section class="setting-card">
                    <header class="card-head">
                        <h3>기본 정보</h3>
                        <span class="card-desc">연락처와 이메일 정보입니다.</span>
                    </header>

                    <div class="field-grid">
                        <div class="form-field">
                            <label>휴대폰 번호</label>
                            <input v-model.trim="form.user_master.user_phone" type="tel"
                                placeholder="예) 010-1234-5678" maxlength="20" autocomplete="off" />
                        </div>

                        <div class="form-field">
                            <label>이메일</label>
                            <input v-model.trim="form.user_master.email" type="email"
                                placeholder="예) example@gmail.com" maxlength="100" autocomplete="off" />
                        </div>
                    </div>
                </section>

                <!-- ════════════ 연동 키 (user_detail) ════════════ -->
                <section class="setting-card">
                    <header class="card-head">
                        <h3>API / 알림 연동 키</h3>
                        <span class="card-desc">민감 정보입니다. 오른쪽 버튼으로 표시/숨김을 전환할 수 있습니다.</span>
                    </header>

                    <div class="field-grid">
                        <div class="form-field">
                            <label>KIS ID</label>
                            <input v-model.trim="form.user_detail.kis_id" type="text"
                                placeholder="한국투자증권 HTS ID" autocomplete="off" spellcheck="false" />
                        </div>

                        <div class="form-field">
                            <label>KIS 계좌번호</label>
                            <input v-model.trim="form.user_detail.kis_account" type="text"
                                placeholder="예) 12345678-01" autocomplete="off" spellcheck="false" />
                        </div>

                        <div class="form-field" v-for="f in detailFields" :key="f.key">
                            <label>{{ f.label }}</label>
                            <div class="secret-input">
                                <input
                                    v-model.trim="form.user_detail[f.key]"
                                    :type="reveal[f.key] ? 'text' : 'password'"
                                    :placeholder="f.placeholder"
                                    autocomplete="new-password"
                                    spellcheck="false" />
                                <button type="button" class="btn-reveal"
                                    @click="reveal[f.key] = !reveal[f.key]"
                                    :aria-label="reveal[f.key] ? '숨기기' : '표시하기'"
                                    :title="reveal[f.key] ? '숨기기' : '표시하기'">
                                    <!-- eye -->
                                    <svg v-if="!reveal[f.key]" width="18" height="18" viewBox="0 0 24 24" fill="none"
                                        stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                                        <path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7-11-7-11-7z" />
                                        <circle cx="12" cy="12" r="3" />
                                    </svg>
                                    <!-- eye-off -->
                                    <svg v-else width="18" height="18" viewBox="0 0 24 24" fill="none"
                                        stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                                        <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
                                        <line x1="1" y1="1" x2="23" y2="23" />
                                    </svg>
                                </button>
                            </div>
                        </div>
                    </div>
                </section>

                <!--
                  ════════════ 확장 영역 ════════════
                  이 위치에 향후 설정 카드들이 추가될 수 있습니다 (여유 공간).
                  user_id = 1 사용자 전용 별도 설정 자리.
                -->
                <section class="setting-card special-card" v-if="isSpecialUser">
                    <header class="card-head">
                        <h3>관리자 설정</h3>
                        <span class="card-desc">user_id = 1 전용 매수 포지션 체크 파라미터입니다.</span>
                    </header>

                    <div class="field-grid two-col">
                        <div class="form-field">
                            <label>거래량 하한 (vol_limit)</label>
                            <input v-model.trim="form.user_options.vol_limit" type="number"
                                placeholder="예) 100000" min="0" step="1" inputmode="numeric" />
                            <span class="field-hint">매수 포지션 체크 시 최소 거래량 수치</span>
                        </div>

                        <div class="form-field">
                            <label>거래량 급증 배수 (vol_surge)</label>
                            <input v-model.trim="form.user_options.vol_surge" type="number"
                                placeholder="예) 2.5" min="0" step="any" inputmode="decimal" />
                            <span class="field-hint">평균 대비 거래량 급증 판단 배수</span>
                        </div>

                        <!-- 추후 관리자 설정 항목이 이 그리드에 2단으로 추가됩니다. -->
                    </div>
                </section>

                <!-- ════════════ 알림 설정 (user_options) ════════════ -->
                <section class="setting-card">
                    <header class="card-head">
                        <h3>알림 설정</h3>
                        <span class="card-desc">메일 알림 수신 여부를 설정합니다.</span>
                    </header>

                    <div class="field-grid">
                        <div class="form-field switch-field">
                            <div class="switch-text">
                                <label>매수 추천 종목 메일 수신</label>
                                <span class="switch-sub">배치가 선정한 매수 추천 종목을 메일로 받습니다.</span>
                            </div>
                            <button type="button"
                                :class="['toggle-btn', form.user_options.stock_buy_target_mail_flag === 'Y' ? 'active' : 'inactive']"
                                @click="toggleMailFlag"
                                role="switch"
                                :aria-checked="form.user_options.stock_buy_target_mail_flag === 'Y'">
                                <span class="toggle-knob"></span>
                            </button>
                        </div>
                    </div>
                </section>

                <!-- ════════════ 저장 바 ════════════ -->
                <div class="save-bar">
                    <span class="dirty-note" v-if="isDirty">변경된 항목이 있습니다.</span>
                    <span class="dirty-note clean" v-else>변경 사항 없음</span>
                    <button type="button" class="btn-reset" @click="resetForm" :disabled="!isDirty || isSaving">되돌리기</button>
                    <button type="submit" class="btn-save" :disabled="!isDirty || isSaving">
                        {{ isSaving ? '저장 중…' : '저장' }}
                    </button>
                </div>

            </form>
        </div>
    </div>
</template>

<script setup>
import aibeesApi from '@scripts/aibeesApi.js';
import { assUserSession } from '@scripts/stores/user-stores';

const title = ref('개인설정');

const userSession = assUserSession();
// user_id = 1 사용자는 별도 주문(추가 설정)이 예정되어 있어 분기 처리.
const isSpecialUser = computed(() => Number(userSession.user.loginInfo.user_id) === 1);

/* ── user_detail 비밀 필드 정의 (DRY) ── */
const detailFields = [
    { key: 'kis_access_key', label: 'KIS Access Key', placeholder: '한국투자증권 App Key' },
    { key: 'kis_secret_key', label: 'KIS Secret Key', placeholder: '한국투자증권 Secret Key' },
    { key: 'tele_bot_id', label: '텔레그램 봇 ID', placeholder: 'Telegram Bot ID' },
    { key: 'tele_chat_id', label: '텔레그램 채팅 ID', placeholder: 'Telegram Chat ID' },
];

// 표시/숨김 상태
const reveal = reactive({});
detailFields.forEach(f => (reveal[f.key] = false));

/* ── 폼 상태: table 명을 1차 key, 컬럼을 하위 key 로 ── */
const blankForm = () => ({
    user_master: { user_phone: '', email: '' },
    user_detail: { kis_id: '', kis_account: '', kis_access_key: '', kis_secret_key: '', tele_bot_id: '', tele_chat_id: '' },
    // vol_limit / vol_surge 는 관리자(user_id=1) 전용 항목
    user_options: { stock_buy_target_mail_flag: 'N', vol_limit: '', vol_surge: '' },
});

const form = reactive(blankForm());
let original = blankForm();   // 변경 비교용 스냅샷

const isLoading = ref(true);
const isSaving = ref(false);

/* ── 조회 ── */
const fetchOptions = async () => {
    isLoading.value = true;
    try {
        // 서버는 JWT 의 user_id 기준 본인 데이터만 반환한다.
        const { data } = await aibeesApi.get('/api/v1/user-options');
        const d = data.data ?? {};

        // 서버 응답(null 안전)으로 폼 채우기
        Object.assign(form.user_master, {
            user_phone: d.user_master?.user_phone ?? '',
            email: d.user_master?.email ?? '',
        });
        Object.assign(form.user_detail, {
            kis_id: d.user_detail?.kis_id ?? '',
            kis_account: d.user_detail?.kis_account ?? '',
            kis_access_key: d.user_detail?.kis_access_key ?? '',
            kis_secret_key: d.user_detail?.kis_secret_key ?? '',
            tele_bot_id: d.user_detail?.tele_bot_id ?? '',
            tele_chat_id: d.user_detail?.tele_chat_id ?? '',
        });
        Object.assign(form.user_options, {
            stock_buy_target_mail_flag: d.user_options?.stock_buy_target_mail_flag ?? 'N',
            // 숫자 컬럼은 비교 일관성을 위해 문자열로 보관
            vol_limit: d.user_options?.vol_limit != null ? String(d.user_options.vol_limit) : '',
            vol_surge: d.user_options?.vol_surge != null ? String(d.user_options.vol_surge) : '',
        });

        original = JSON.parse(JSON.stringify(form));
    } finally {
        isLoading.value = false;
    }
};

onMounted(fetchOptions);

/* ── 토글 ── */
const toggleMailFlag = () => {
    form.user_options.stock_buy_target_mail_flag =
        form.user_options.stock_buy_target_mail_flag === 'Y' ? 'N' : 'Y';
};

/* ── 변경분(diff) 계산: table 별로 바뀐 컬럼만 ── */
const buildDiff = () => {
    const diff = {};
    for (const table of Object.keys(form)) {
        const changed = {};
        for (const key of Object.keys(form[table])) {
            if (form[table][key] !== original[table]?.[key]) {
                changed[key] = form[table][key];
            }
        }
        if (Object.keys(changed).length > 0) diff[table] = changed;
    }
    return diff;
};

const isDirty = computed(() => Object.keys(buildDiff()).length > 0);

/* ── 되돌리기 ── */
const resetForm = () => {
    const snap = JSON.parse(JSON.stringify(original));
    Object.assign(form.user_master, snap.user_master);
    Object.assign(form.user_detail, snap.user_detail);
    Object.assign(form.user_options, snap.user_options);
};

/* ── 저장: 변경된 table/컬럼만 전송 ── */
const save = async () => {
    const payload = buildDiff();
    if (Object.keys(payload).length === 0) {
        alert('변경된 항목이 없습니다.');
        return;
    }

    // 숫자 컬럼은 number(또는 빈 값이면 null)로 변환해 전송
    if (payload.user_options) {
        for (const k of ['vol_limit', 'vol_surge']) {
            if (k in payload.user_options) {
                const v = payload.user_options[k];
                payload.user_options[k] = v === '' ? null : Number(v);
            }
        }
    }

    isSaving.value = true;
    try {
        // body 예) { "user_master": { "email": "..." }, "user_options": { "stock_buy_target_mail_flag": "Y" } }
        await aibeesApi.patch('/api/v1/user-options', payload);
        original = JSON.parse(JSON.stringify(form));   // 저장 성공 → 스냅샷 갱신
        alert('저장되었습니다.');
    } finally {
        isSaving.value = false;
    }
};
</script>

<style scoped>
#user-option {
    min-height: 100vh;
    background: #f4f6f9;
}

.contents {
    max-width: 720px;
    margin: 0 auto;
    padding: 16px 14px 96px;
    box-sizing: border-box;
}

/* ── 상단 타이틀 ── */
.head-desc {
    padding: 8px 4px 16px;
}

.head-desc h2 {
    margin: 0;
    font-size: 1.25rem;
    font-weight: 700;
    color: #1f2329;
}

.head-desc .sub-text {
    margin: 6px 0 0;
    font-size: 0.85rem;
    color: #6b7280;
    line-height: 1.4;
}

/* ── 카드 ── */
.setting-card {
    background: #fff;
    border: 1px solid #e5e8ec;
    border-radius: 14px;
    padding: 18px 18px 20px;
    margin-bottom: 14px;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
}

.card-head {
    margin-bottom: 14px;
}

.card-head h3 {
    margin: 0;
    font-size: 1rem;
    font-weight: 700;
    color: #2db400;
}

.card-head .card-desc {
    display: block;
    margin-top: 4px;
    font-size: 0.78rem;
    color: #8a929c;
    line-height: 1.4;
}

.special-card {
    border-style: dashed;
    border-color: #c9d3dd;
    background: #fafcff;
}

.placeholder-note {
    margin: 0;
    font-size: 0.85rem;
    color: #9aa3ad;
}

/* ── 필드 ── */
.field-grid {
    display: flex;
    flex-direction: column;
    gap: 14px;
}

/* 2단 그리드 (관리자 설정 등) */
.field-grid.two-col {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 14px 16px;
}

.field-hint {
    font-size: 0.74rem;
    color: #9aa3ad;
    line-height: 1.3;
}

.form-field {
    display: flex;
    flex-direction: column;
    gap: 6px;
}

.form-field label {
    font-size: 0.85rem;
    font-weight: 600;
    color: #3b4149;
}

.form-field input {
    width: 100%;
    box-sizing: border-box;
    height: 44px;
    padding: 0 12px;
    border: 1px solid #d6dbe1;
    border-radius: 10px;
    font-size: 0.92rem;
    color: #1f2329;
    background: #fff;
    transition: border-color 0.15s, box-shadow 0.15s;
}

.form-field input:focus {
    outline: none;
    border-color: #2db400;
    box-shadow: 0 0 0 3px rgba(45, 180, 0, 0.12);
}

.form-field input::placeholder {
    color: #b3bac2;
}

/* ── 비밀 입력 + 표시 토글 ── */
.secret-input {
    position: relative;
    display: flex;
    align-items: center;
}

.secret-input input {
    padding-right: 46px;
}

.btn-reveal {
    position: absolute;
    right: 6px;
    top: 50%;
    transform: translateY(-50%);
    width: 34px;
    height: 34px;
    display: grid;
    place-items: center;
    border: 0;
    background: transparent;
    color: #8a929c;
    cursor: pointer;
    border-radius: 8px;
}

.btn-reveal:hover {
    color: #2db400;
    background: rgba(45, 180, 0, 0.08);
}

/* ── 스위치 필드 ── */
.switch-field {
    flex-direction: row;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
}

.switch-text {
    display: flex;
    flex-direction: column;
    gap: 3px;
}

.switch-text label {
    font-size: 0.9rem;
}

.switch-sub {
    font-size: 0.76rem;
    color: #8a929c;
    line-height: 1.3;
}

.toggle-btn {
    flex: 0 0 auto;
    width: 46px;
    height: 26px;
    border-radius: 999px;
    border: 0;
    position: relative;
    cursor: pointer;
    transition: background 0.18s;
    background: #cfd6de;
}

.toggle-btn.active {
    background: #2db400;
}

.toggle-knob {
    position: absolute;
    top: 3px;
    left: 3px;
    width: 20px;
    height: 20px;
    background: #fff;
    border-radius: 50%;
    transition: transform 0.18s;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
}

.toggle-btn.active .toggle-knob {
    transform: translateX(20px);
}

/* ── 저장 바 ── */
.save-bar {
    position: sticky;
    bottom: 0;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 12px 14px;
    margin: 4px -14px 0;
    background: rgba(255, 255, 255, 0.92);
    backdrop-filter: blur(6px);
    border-top: 1px solid #e5e8ec;
}

.dirty-note {
    flex: 1;
    font-size: 0.8rem;
    color: #d97706;
    font-weight: 600;
}

.dirty-note.clean {
    color: #9aa3ad;
    font-weight: 500;
}

.btn-reset,
.btn-save {
    height: 42px;
    padding: 0 18px;
    border-radius: 10px;
    font-size: 0.9rem;
    font-weight: 600;
    cursor: pointer;
    border: 1px solid transparent;
}

.btn-reset {
    background: #fff;
    border-color: #d6dbe1;
    color: #5b636c;
}

.btn-reset:disabled {
    opacity: 0.5;
    cursor: default;
}

.btn-save {
    background: #2db400;
    color: #fff;
}

.btn-save:disabled {
    background: #add9a0;
    cursor: default;
}

/* ── 로딩 스켈레톤 ── */
.loader-rows {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.skeleton-row {
    height: 96px;
    border-radius: 14px;
    background: linear-gradient(90deg, #eceff3 25%, #f5f7f9 50%, #eceff3 75%);
    background-size: 200% 100%;
    animation: shimmer 1.2s infinite;
}

@keyframes shimmer {
    0% { background-position: 200% 0; }
    100% { background-position: -200% 0; }
}

/* ── 모바일 ── */
@media (max-width: 768px) {
    .contents {
        padding: 12px 10px 96px;
    }

    .setting-card {
        padding: 16px 14px 18px;
        border-radius: 12px;
    }

    .head-desc h2 {
        font-size: 1.15rem;
    }

    /* 모바일에서는 2단 → 1단 */
    .field-grid.two-col {
        grid-template-columns: 1fr;
    }
}
</style>
