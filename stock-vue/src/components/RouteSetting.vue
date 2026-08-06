<template>
    <div id="route-setting">
        <Headers :prop_title="title" />

        <div class="contents">

            <!-- ── 상단 타이틀 + 추가 버튼 ── -->
            <section class="head-desc">
                <div class="head-left">
                    <h2>메뉴 라우트 설정</h2>
                    <p class="sub-text">시스템에 등록된 메뉴 경로를 관리합니다</p>
                </div>
                <button class="btn-add" @click="openAdd">
                    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24"
                        fill="none" stroke="currentColor" stroke-width="2.5"
                        stroke-linecap="round" stroke-linejoin="round">
                        <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
                    </svg>
                    메뉴 추가
                </button>
            </section>

            <!-- ── 테이블 ── -->
            <section class="table-section">
                <div v-if="isLoading" class="loader-rows">
                    <div v-for="n in 6" :key="n" class="skeleton-row"></div>
                </div>

                <table v-else class="menu-table">
                    <thead>
                        <tr>
                            <th class="col-sort">순서</th>
                            <th class="col-code">코드</th>
                            <th class="col-parent">부모</th>
                            <th class="col-name">메뉴명</th>
                            <th class="col-path">경로</th>
                            <th class="col-title">타이틀</th>
                            <th class="col-component">컴포넌트</th>
                            <th class="col-flag">표시</th>
                            <th class="col-flag">활성</th>
                            <th class="col-admin">관리자</th>
                            <th class="col-action"></th>
                        </tr>
                    </thead>
                    <tbody>
                        <template v-for="row in flatList" :key="row.menu_code">
                            <tr :class="{ 'row-disabled': row.enabled_flag === 'N', 'row-child': row.menu_parents !== 'ROOT' }">
                                <td class="col-sort">{{ row.sort }}</td>
                                <td class="col-code"><span class="code-chip">{{ row.menu_code }}</span></td>
                                <td class="col-parent">
                                    <span v-if="row.menu_parents !== 'ROOT'" class="parent-chip">{{ row.menu_parents }}</span>
                                    <span v-else class="root-label">ROOT</span>
                                </td>
                                <td class="col-name">
                                    <span :class="['indent', { child: row.menu_parents !== 'ROOT' }]">{{ row.menu_name }}</span>
                                </td>
                                <td class="col-path"><span class="path-text">{{ row.menu_path }}</span></td>
                                <td class="col-title">{{ row.menu_title ?? '-' }}</td>
                                <td class="col-component"><span class="comp-text">{{ row.menu_component }}</span></td>
                                <td class="col-flag">
                                    <span :class="['flag-badge', row.display_flag === 'Y' ? 'on' : 'off']">
                                        {{ row.display_flag === 'Y' ? '표시' : '숨김' }}
                                    </span>
                                </td>
                                <td class="col-flag">
                                    <button
                                        :class="['toggle-btn', row.enabled_flag === 'Y' ? 'active' : 'inactive']"
                                        @click="toggleEnabled(row)"
                                        :disabled="togglingCode === row.menu_code"
                                    >
                                        <span class="toggle-knob"></span>
                                    </button>
                                </td>
                                <td class="col-admin">
                                    <span :class="['flag-badge', row.admin_only === 'Y' ? 'admin' : 'off']">
                                        {{ row.admin_only === 'Y' ? '전용' : '-' }}
                                    </span>
                                </td>
                                <td class="col-action">
                                    <button class="btn-edit" @click="openEdit(row)">수정</button>
                                </td>
                            </tr>
                        </template>
                        <tr v-if="!isLoading && flatList.length === 0">
                            <td colspan="11" class="empty-cell">등록된 메뉴가 없습니다.</td>
                        </tr>
                    </tbody>
                </table>
            </section>
        </div>

        <!-- ── 레이어 팝업 ── -->
        <Teleport to="body">
            <Transition name="fade">
                <div v-if="popup.visible" class="popup-overlay">
                    <div class="popup-panel" v-draggable>

                        <div class="popup-header">
                            <h3>{{ popup.isEdit ? '메뉴 수정' : '메뉴 추가' }}</h3>
                            <button class="btn-close" @click="closePopup">
                                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24"
                                    fill="none" stroke="currentColor" stroke-width="2"
                                    stroke-linecap="round" stroke-linejoin="round">
                                    <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                                </svg>
                            </button>
                        </div>

                        <div class="popup-body">
                            <div class="form-grid">

                                <!-- 메뉴 코드 -->
                                <div class="form-field">
                                    <label>메뉴 코드 <span class="req">*</span></label>
                                    <input v-model="form.menu_code" :disabled="popup.isEdit"
                                        placeholder="예) STOCK_LIST" maxlength="64" />
                                </div>

                                <!-- 부모 코드 -->
                                <div class="form-field">
                                    <label>부모 코드 <span class="req">*</span></label>
                                    <input v-model="form.menu_parents" placeholder="예) ROOT 또는 부모 코드" maxlength="45" />
                                </div>

                                <!-- 메뉴명 -->
                                <div class="form-field">
                                    <label>메뉴명 <span class="req">*</span></label>
                                    <input v-model="form.menu_name" placeholder="예) 주식" maxlength="45" />
                                </div>

                                <!-- 경로 -->
                                <div class="form-field">
                                    <label>경로 (path) <span class="req">*</span></label>
                                    <input v-model="form.menu_path" placeholder="예) stocks" maxlength="45" />
                                </div>

                                <!-- 타이틀 -->
                                <div class="form-field full">
                                    <label>타이틀</label>
                                    <input v-model="form.menu_title" placeholder="LNB·메뉴에 표시되는 레이블" maxlength="200" />
                                </div>

                                <!-- 컴포넌트 -->
                                <div class="form-field full">
                                    <label>컴포넌트 <span class="req">*</span></label>
                                    <input v-model="form.menu_component" placeholder="예) StockView" maxlength="45" />
                                </div>

                                <!-- 정렬 순서 -->
                                <div class="form-field">
                                    <label>정렬 순서 <span class="req">*</span></label>
                                    <input v-model.number="form.sort" type="number" min="0" placeholder="0" />
                                </div>

                                <!-- 표시 여부 -->
                                <div class="form-field">
                                    <label>표시 여부 <span class="req">*</span></label>
                                    <div class="radio-group">
                                        <label class="radio-label">
                                            <input type="radio" v-model="form.display_flag" value="Y" /> 표시
                                        </label>
                                        <label class="radio-label">
                                            <input type="radio" v-model="form.display_flag" value="N" /> 숨김
                                        </label>
                                    </div>
                                </div>

                                <!-- 활성화 -->
                                <div class="form-field">
                                    <label>활성화 <span class="req">*</span></label>
                                    <div class="radio-group">
                                        <label class="radio-label">
                                            <input type="radio" v-model="form.enabled_flag" value="Y" /> 활성
                                        </label>
                                        <label class="radio-label">
                                            <input type="radio" v-model="form.enabled_flag" value="N" /> 비활성
                                        </label>
                                    </div>
                                </div>

                                <!-- 관리자 전용 -->
                                <div class="form-field">
                                    <label>관리자 전용 <span class="req">*</span></label>
                                    <div class="radio-group">
                                        <label class="radio-label">
                                            <input type="radio" v-model="form.admin_only" value="Y" /> 전용
                                        </label>
                                        <label class="radio-label">
                                            <input type="radio" v-model="form.admin_only" value="N" /> 일반
                                        </label>
                                    </div>
                                </div>

                            </div>
                        </div>

                        <div class="popup-footer">
                            <button class="btn-cancel" @click="closePopup">취소</button>
                            <button class="btn-save" @click="saveMenu" :disabled="isSaving">
                                {{ isSaving ? '저장 중…' : (popup.isEdit ? '수정 완료' : '추가') }}
                            </button>
                        </div>

                    </div>
                </div>
            </Transition>
        </Teleport>

    </div>
</template>

<script setup>
import Headers from './common/comp/Headers.vue';
import Lnb from './common/Lnb.vue';
import aibeesApi from '@scripts/aibeesApi.js';

const title = ref('메뉴 설정');

/* ── 목록 ── */
const rawList    = ref([]);
const isLoading  = ref(true);
const togglingCode = ref(null);

const flatList = computed(() => {
    const result = [];
    for (const m of rawList.value) {
        result.push(m);
        if (m.children?.length) {
            result.push(...m.children);
        }
    }
    return result;
});

const fetchMenus = async () => {
    isLoading.value = true;
    try {
        const { data } = await aibeesApi.get('/api/v1/master/menus');
        rawList.value = data.data ?? [];
    } finally {
        isLoading.value = false;
    }
};

onMounted(fetchMenus);

/* ── 활성화 토글 (PATCH) ── */
const toggleEnabled = async (row) => {
    togglingCode.value = row.menu_code;
    const next = row.enabled_flag === 'Y' ? 'N' : 'Y';
    try {
        await aibeesApi.patch(`/api/v1/master/menus/${row.menu_code}`, { enabled_flag: next });
        row.enabled_flag = next;
    } finally {
        togglingCode.value = null;
    }
};

/* ── 팝업 ── */
const defaultForm = () => ({
    menu_code: '',
    menu_parents: '',
    menu_name: '',
    menu_path: '',
    enabled_flag: 'Y',
    display_flag: 'Y',
    menu_component: '',
    menu_title: '',
    sort: 0,
    admin_only: 'N',
});

const popup   = reactive({ visible: false, isEdit: false });
const form    = reactive(defaultForm());
const isSaving = ref(false);

const openAdd = () => {
    Object.assign(form, defaultForm());
    popup.isEdit   = false;
    popup.visible  = true;
};

const openEdit = (row) => {
    Object.assign(form, { ...row });
    popup.isEdit   = true;
    popup.visible  = true;
};

const closePopup = () => { popup.visible = false; };

const saveMenu = async () => {
    if (!form.menu_code || !form.menu_name || !form.menu_path || !form.menu_component) {
        alert('필수 항목을 모두 입력해 주세요.');
        return;
    }
    isSaving.value = true;
    try {
        if (popup.isEdit) {
            await aibeesApi.put(`/api/v1/master/menus/${form.menu_code}`, { ...form });
        } else {
            await aibeesApi.post('/api/v1/master/menus', { ...form });
        }
        closePopup();
        await fetchMenus();
    } finally {
        isSaving.value = false;
    }
};
</script>

<style scoped lang="scss">
$white:    #ffffff;
$gray-50:  #f8f9fa;
$gray-100: #ebebeb;
$gray-200: #d0d0d0;
$gray-400: #909090;
$gray-500: #6b6b6b;
$gray-700: #333333;
$gray-900: #111111;
$blue:     #1971c2;
$navy:     #1c3d6e;
$red:      #c92a2a;
$amber:    #e67700;
$green:    #2f9e44;

#route-setting {
    min-height: 100vh;
    background: $gray-50;
    color: $gray-900;
    font-family: 'Pretendard', -apple-system, sans-serif;
}

.contents {
    max-width: 1200px;
    margin: 0 auto;
    padding: 28px 16px 100px;
}

/* ── Head ── */
.head-desc {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    margin-bottom: 20px;

    h2 {
        font-size: 1.4rem;
        font-weight: 700;
        margin: 0;
        color: $gray-900;
    }

    .sub-text {
        font-size: 0.82rem;
        color: $gray-500;
        margin: 4px 0 0;
    }
}

.btn-add {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 8px 16px;
    background: $navy;
    color: $white;
    border: none;
    border-radius: 0.4rem;
    font-size: 0.84rem;
    font-weight: 600;
    cursor: pointer;
    font-family: inherit;
    transition: background .15s;

    &:hover { background: darken(#1c3d6e, 6%); }
}

/* ── Table ── */
.table-section {
    background: $white;
    border: 1px solid $gray-200;
    border-radius: 0.6rem;
    overflow: hidden;
}

.menu-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.83rem;

    thead tr {
        background: $gray-50;
        border-bottom: 1px solid $gray-200;
    }

    th {
        padding: 10px 12px;
        text-align: left;
        font-size: 0.72rem;
        font-weight: 700;
        color: $gray-500;
        letter-spacing: .04em;
        text-transform: uppercase;
        white-space: nowrap;
    }

    td {
        padding: 10px 12px;
        border-bottom: 1px solid $gray-100;
        vertical-align: middle;
        color: $gray-700;
    }

    tbody tr:last-child td { border-bottom: none; }

    tbody tr:hover td { background: $gray-50; }

    .row-disabled td { opacity: .45; }

    .row-child td:first-child { padding-left: 24px; }
}

/* column widths */
.col-sort      { width: 52px; text-align: center; }
.col-code      { width: 140px; }
.col-parent    { width: 110px; }
.col-name      { width: 110px; }
.col-path      { width: 110px; }
.col-title     { min-width: 120px; }
.col-component { width: 120px; }
.col-flag      { width: 70px; text-align: center; }
.col-admin     { width: 70px; text-align: center; }
.col-action    { width: 60px; text-align: center; }

/* chips */
.code-chip {
    font-size: 0.72rem;
    font-weight: 600;
    background: $gray-100;
    color: $gray-700;
    padding: 2px 7px;
    border-radius: 0.3rem;
    border: 1px solid $gray-200;
}

.parent-chip {
    font-size: 0.72rem;
    background: #dbe4ff;
    color: $navy;
    padding: 2px 7px;
    border-radius: 0.3rem;
    border: 1px solid #bac8ff;
}

.root-label {
    font-size: 0.72rem;
    color: $gray-400;
}

.path-text, .comp-text {
    font-family: 'SFMono-Regular', Consolas, monospace;
    font-size: 0.78rem;
    color: $gray-700;
}

.indent.child::before {
    content: '└ ';
    color: $gray-400;
}

/* flag badge */
.flag-badge {
    font-size: 0.7rem;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 0.3rem;

    &.on    { background: #d3f9d8; color: $green; border: 1px solid #8ce99a; }
    &.off   { background: $gray-100; color: $gray-400; border: 1px solid $gray-200; }
    &.admin { background: #fff0b3; color: $amber; border: 1px solid #ffd43b; }
}

/* toggle */
.toggle-btn {
    position: relative;
    width: 36px;
    height: 20px;
    border-radius: 10px;
    border: none;
    cursor: pointer;
    transition: background .2s;
    padding: 0;

    &.active   { background: $green; }
    &.inactive { background: $gray-200; }

    &:disabled { opacity: .5; cursor: not-allowed; }

    .toggle-knob {
        position: absolute;
        top: 3px;
        width: 14px;
        height: 14px;
        border-radius: 50%;
        background: $white;
        transition: left .2s;
    }

    &.active   .toggle-knob { left: 19px; }
    &.inactive .toggle-knob { left: 3px; }
}

.btn-edit {
    padding: 4px 10px;
    font-size: 0.75rem;
    font-weight: 600;
    border: 1px solid $gray-200;
    border-radius: 0.3rem;
    background: $white;
    color: $gray-700;
    cursor: pointer;
    font-family: inherit;
    transition: border-color .12s, color .12s;

    &:hover { border-color: $blue; color: $blue; }
}

/* skeleton */
.loader-rows { padding: 8px; }
.skeleton-row {
    height: 42px;
    background: $gray-100;
    border-radius: 0.4rem;
    margin-bottom: 6px;
    animation: pulse 1.6s infinite ease-in-out;
}

.empty-cell {
    text-align: center;
    padding: 60px 0;
    color: $gray-400;
    font-size: 0.88rem;
}

/* ── Popup ── */
.popup-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, .45);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 2000;
    padding: 16px;
}

.popup-panel {
    background: $white;
    border-radius: 0.7rem;
    width: 100%;
    max-width: 560px;
    max-height: 90vh;
    display: flex;
    flex-direction: column;
    box-shadow: 0 8px 40px rgba(0,0,0,.18);
}

.popup-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 18px 20px 14px;
    border-bottom: 1px solid $gray-100;

    h3 {
        margin: 0;
        font-size: 1rem;
        font-weight: 700;
        color: $gray-900;
    }

    .btn-close {
        border: none;
        background: none;
        cursor: pointer;
        color: $gray-400;
        padding: 4px;
        border-radius: 0.3rem;
        display: flex;
        align-items: center;
        transition: color .12s;

        &:hover { color: $gray-900; }
    }
}

.popup-body {
    padding: 20px;
    overflow-y: auto;
    flex: 1;
}

.form-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 14px 16px;

    .form-field {
        display: flex;
        flex-direction: column;
        gap: 5px;

        &.full { grid-column: 1 / -1; }

        label {
            font-size: 0.78rem;
            font-weight: 600;
            color: $gray-700;
        }

        .req { color: $red; margin-left: 2px; }

        input[type="text"],
        input[type="number"],
        input:not([type="radio"]) {
            padding: 8px 10px;
            border: 1px solid $gray-200;
            border-radius: 0.4rem;
            font-size: 0.84rem;
            color: $gray-900;
            font-family: inherit;
            background: $white;
            outline: none;
            transition: border-color .15s;

            &:focus  { border-color: $blue; }
            &:disabled { background: $gray-50; color: $gray-400; }
            &::placeholder { color: $gray-400; }
        }

        .radio-group {
            display: flex;
            gap: 16px;
            padding: 8px 0 4px;
        }

        .radio-label {
            display: flex;
            align-items: center;
            gap: 5px;
            font-size: 0.84rem;
            font-weight: 500;
            color: $gray-700;
            cursor: pointer;

            input[type="radio"] { cursor: pointer; accent-color: $navy; }
        }
    }
}

.popup-footer {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    padding: 14px 20px 18px;
    border-top: 1px solid $gray-100;

    .btn-cancel {
        padding: 8px 18px;
        border: 1px solid $gray-200;
        border-radius: 0.4rem;
        background: $white;
        color: $gray-700;
        font-size: 0.84rem;
        font-weight: 600;
        cursor: pointer;
        font-family: inherit;
        transition: border-color .12s;

        &:hover { border-color: $gray-400; }
    }

    .btn-save {
        padding: 8px 20px;
        border: none;
        border-radius: 0.4rem;
        background: $navy;
        color: $white;
        font-size: 0.84rem;
        font-weight: 700;
        cursor: pointer;
        font-family: inherit;
        transition: background .15s;

        &:hover    { background: darken(#1c3d6e, 6%); }
        &:disabled { opacity: .55; cursor: not-allowed; }
    }
}

/* ── Transition ── */
.fade-enter-active, .fade-leave-active { transition: opacity .18s; }
.fade-enter-from,  .fade-leave-to      { opacity: 0; }

@keyframes pulse {
    0%, 100% { opacity: .5; }
    50%       { opacity: .9; }
}
</style>
