<template>
    <div id="route-setting">
        <BrandHeader :title="title" back="/menu" />

        <div class="contents">

            <!-- ── 요약 + 추가 버튼 ── -->
            <section class="toolbar">
                <p class="summary">메뉴 <b>{{ totalCount }}</b>개 · 비활성 {{ disabledCount }}</p>
                <button type="button" class="btn-primary" @click="openAdd">+ 메뉴 추가</button>
            </section>

            <div v-if="isLoading" class="loader-rows">
                <div v-for="n in 6" :key="n" class="skeleton-row"></div>
            </div>

            <!-- ── 메뉴 트리: 최상위 메뉴 = 그룹 제목, 하위 메뉴 = 구분선 목록(카드 없음) ── -->
            <template v-else>
                <section v-for="root in tree" :key="root.menu_code" class="menu-group">
                    <div class="group-head" :class="{ off: root.enabled_flag === 'N' }">
                        <div class="gh-title">
                            <div class="gh-line">
                                <h2>{{ labelOf(root) }}</h2>
                                <span v-for="t in tagsOf(root)" :key="t.text" class="tag" :class="t.cls">{{ t.text }}</span>
                            </div>
                            <span class="route-path">{{ fullPath(root) }}</span>
                        </div>
                        <div class="gh-right">
                            <button type="button" class="act" @click="openEdit(root)">수정</button>
                            <button type="button" :class="['toggle-btn', root.enabled_flag === 'Y' ? 'active' : 'inactive']"
                                role="switch" :aria-checked="root.enabled_flag === 'Y' ? 'true' : 'false'"
                                :aria-label="`${labelOf(root)} 활성`"
                                @click="toggleEnabled(root)" :disabled="togglingCode === root.menu_code">
                                <span class="toggle-knob"></span>
                            </button>
                        </div>
                    </div>

                    <ul v-if="root.children && root.children.length" class="menu-list">
                        <li v-for="c in childrenOf(root)" :key="c.menu_code" class="menu" :class="{ off: c.enabled_flag === 'N' }">
                            <div class="m-top">
                                <div class="m-title">
                                    <span class="m-name">{{ labelOf(c) }}</span>
                                    <span v-for="t in tagsOf(c)" :key="t.text" class="tag" :class="t.cls">{{ t.text }}</span>
                                </div>
                                <button type="button" :class="['toggle-btn', c.enabled_flag === 'Y' ? 'active' : 'inactive']"
                                    role="switch" :aria-checked="c.enabled_flag === 'Y' ? 'true' : 'false'"
                                    :aria-label="`${labelOf(c)} 활성`"
                                    @click="toggleEnabled(c)" :disabled="togglingCode === c.menu_code">
                                    <span class="toggle-knob"></span>
                                </button>
                            </div>
                            <div class="m-route">
                                <span class="route-path">{{ fullPath(c, root) }}</span>
                            </div>
                            <div class="m-foot">
                                <!-- 컴포넌트명은 메뉴 코드와 다를 때만(대부분 같아 반복되던 것) -->
                                <span class="m-tech">{{ c.menu_code }}<template v-if="c.menu_component && c.menu_component !== c.menu_code"> · {{ c.menu_component }}</template> · 순서 {{ c.sort }}</span>
                                <button type="button" class="act" @click="openEdit(c)">수정</button>
                            </div>
                        </li>
                    </ul>
                </section>
                <p v-if="!tree.length" class="empty">등록된 메뉴가 없습니다.</p>
            </template>
        </div>

        <!-- ── 레이어 팝업 ── -->
        <Teleport to="body">
            <Transition name="fade">
                <div v-if="popup.visible" class="popup-overlay" @click.self="closePopup">
                    <div class="popup-panel" v-draggable>

                        <div class="popup-header">
                            <h3>{{ popup.isEdit ? '메뉴 수정' : '메뉴 추가' }}</h3>
                            <button class="btn-close" @click="closePopup">
                                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24"
                                    fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"
                                    stroke-linejoin="round">
                                    <line x1="18" y1="6" x2="6" y2="18" />
                                    <line x1="6" y1="6" x2="18" y2="18" />
                                </svg>
                            </button>
                        </div>

                        <div class="popup-body">
                            <div class="form-grid">

                                <!-- 메뉴 코드 -->
                                <div class="form-field">
                                    <label>메뉴 코드 <span class="req">*</span></label>
                                    <input v-model="form.menu_code" :disabled="popup.isEdit" placeholder="예) STOCK_LIST"
                                        maxlength="64" />
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

                                <!-- 공통 메뉴 (권한 매핑 없이 로그인 사용자 전체 허용) -->
                                <div class="form-field">
                                    <label>공통 메뉴 <span class="req">*</span></label>
                                    <div class="radio-group">
                                        <label class="radio-label">
                                            <input type="radio" v-model="form.common_flag" value="Y" /> 공통
                                        </label>
                                        <label class="radio-label">
                                            <input type="radio" v-model="form.common_flag" value="N" /> 권한별
                                        </label>
                                    </div>
                                </div>

                                <!-- 공개 메뉴 (비로그인도 접근 가능) -->
                                <div class="form-field">
                                    <label>공개 메뉴 <span class="req">*</span></label>
                                    <div class="radio-group">
                                        <label class="radio-label">
                                            <input type="radio" v-model="form.public_flag" value="Y" /> 비로그인 허용
                                        </label>
                                        <label class="radio-label">
                                            <input type="radio" v-model="form.public_flag" value="N" /> 로그인 필요
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
import aibeesApi from '@scripts/aibeesApi.js';

const title = ref('라우팅 관리');

/* ── 목록 ── */
const rawList = ref([]);
const isLoading = ref(true);
const togglingCode = ref(null);

// /master/menus 는 최상위 메뉴 배열 + 각자의 children. 그룹/하위 모두 정렬 순서대로.
// (예전 화면은 최상위를 'ROOT' 로 비교했는데 DB 값은 'root' 라 전부 하위 메뉴로 그려졌다)
const bySort = (a, b) => (a.sort ?? 0) - (b.sort ?? 0);
// 원본 객체를 그대로 쓴다(복사하면 활성 토글이 복사본만 바꿔 화면이 되돌아간다)
const tree = computed(() => [...rawList.value].sort(bySort));
const childrenOf = (r) => [...(r.children ?? [])].sort(bySort);
const allMenus = computed(() => tree.value.flatMap(r => [r, ...(r.children ?? [])]));
const totalCount = computed(() => allMenus.value.length);
const disabledCount = computed(() => allMenus.value.filter(m => m.enabled_flag === 'N').length);

const labelOf = (m) => m.menu_title || m.menu_name;
const norm = (p) => String(p ?? '').replace(/^\/+|\/+$/g, '');
// router.js 와 같은 규칙: 하위 메뉴 경로 = /부모경로/자기경로
const fullPath = (m, parent) => (parent ? `/${norm(parent.menu_path)}/${norm(m.menu_path)}` : `/${norm(m.menu_path)}`);

// 상태 태그: 접근 범위(공개 > 공통 > 관리자) + 숨김/비활성
const tagsOf = (m) => {
    const tags = [];
    if (m.public_flag === 'Y') tags.push({ text: '공개', cls: 'pub' });
    else if (m.common_flag === 'Y') tags.push({ text: '공통', cls: 'com' });
    if (m.admin_only === 'Y') tags.push({ text: '관리자', cls: 'adm' });
    if (m.display_flag === 'N') tags.push({ text: '숨김', cls: 'mute' });
    if (m.enabled_flag === 'N') tags.push({ text: '비활성', cls: 'mute' });
    return tags;
};

const fetchMenus = async () => {
    isLoading.value = true;
    try {
        const { data } = await aibeesApi.get('/api/v1/master/menus');
        rawList.value = data.data ?? [];
    } finally {
        isLoading.value = false;
    }
};

onMounted(async () => {
    await fetchMenus();
});

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
    common_flag: 'N',
    public_flag: 'N',
});

const popup = reactive({ visible: false, isEdit: false });
const form = reactive(defaultForm());
const isSaving = ref(false);

const openAdd = () => {
    Object.assign(form, defaultForm());
    popup.isEdit = false;
    popup.visible = true;
};

const openEdit = (row) => {
    Object.assign(form, { ...row });
    popup.isEdit = true;
    popup.visible = true;
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
// 양봉상회 토큰(홈·배치 관리와 동일). 카드 없이 흰 배경 + 구분선.
$white:   #ffffff;
$line:    #EFE2BC;
$line-2:  #EAD9A6;
$chip:    #F6EBC8;
$hero:    #74462A;
$brown:   #7A4423;
$ink:     #2B1D14;
$sub:     #6B5B4E;
$sub-2:   #7A6B5D;
$cream:   #FFF8E1;
$red:     #C8282A;

#route-setting {
    min-height: 100vh;
    background: $white;
    color: $ink;
    text-align: left;
    font-family: 'Pretendard', 'IBM Plex Sans KR', -apple-system, 'Apple SD Gothic Neo', sans-serif;
    font-variant-numeric: tabular-nums;
}

.contents {
    max-width: 760px;
    margin: 0 auto;
    padding: 16px 16px calc(96px + env(safe-area-inset-bottom, 0px));
}

/* ── 요약 + 추가 ── */
.toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    margin-bottom: 4px;
    .summary { margin: 0; font-size: 14px; color: $sub; b { color: $ink; font-size: 16px; } }
}
.btn-primary {
    min-height: 40px;
    padding: 0 14px;
    border: 0;
    border-radius: 10px;
    background: $hero;
    color: $cream;
    font-size: 14px;
    font-weight: 600;
    font-family: inherit;
    cursor: pointer;
    white-space: nowrap;
    &:focus-visible { outline: 2px solid $brown; outline-offset: 2px; }
}

/* ── 그룹(최상위 메뉴) ── */
.menu-group { margin-top: 18px; }
.group-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
    padding-bottom: 8px;
    border-bottom: 1px solid $line;

    &.off .gh-title { opacity: .55; }
}
.gh-title { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.gh-line { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 6px; }
.gh-line h2 { margin: 0; font-size: 17px; font-weight: 700; color: $ink; }
.gh-right { display: flex; align-items: center; gap: 6px; flex-shrink: 0; }

.route-path {
    font-family: ui-monospace, 'SFMono-Regular', Menlo, monospace;
    font-size: 12.5px;
    color: $brown;
    overflow-wrap: anywhere;
}

/* ── 하위 메뉴 목록 ── */
.menu-list { margin: 0; padding: 0; list-style: none; }
.menu {
    display: flex;
    flex-direction: column;
    gap: 4px;
    padding: 12px 0;
    border-bottom: 1px solid $line;

    &.off .m-title,
    &.off .m-route { opacity: .55; }
}
.m-top { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.m-title { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 6px; min-width: 0; }
.m-name { font-size: 15px; font-weight: 600; color: $ink; }
.m-route { display: flex; flex-wrap: wrap; align-items: baseline; gap: 2px 10px; }
.m-foot { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.m-tech {
    min-width: 0;
    font-family: ui-monospace, 'SFMono-Regular', Menlo, monospace;
    font-size: 11.5px;
    color: $sub-2;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

// 상태 태그: 글자로 의미를 전한다(색은 보조)
.tag {
    padding: 1px 7px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 700;
    white-space: nowrap;
    &.pub  { background: #E6F3EA; color: #23784A; }
    &.com  { background: $chip; color: $brown; }
    &.adm  { background: #F3E3D6; color: #8A3F14; }
    &.mute { background: #F1ECE2; color: $sub; }
}

.act {
    min-height: 32px;
    padding: 0 8px;
    border: 0;
    border-radius: 8px;
    background: transparent;
    color: $brown;
    font-size: 13px;
    font-weight: 600;
    font-family: inherit;
    cursor: pointer;
    flex-shrink: 0;
    &:hover { background: rgba(239, 226, 188, .4); }
    &:focus-visible { outline: 2px solid $brown; outline-offset: 0; }
}

/* ── 활성 스위치 ── */
.toggle-btn {
    position: relative;
    flex-shrink: 0;
    width: 44px;
    height: 26px;
    border: 0;
    border-radius: 13px;
    cursor: pointer;
    transition: background .15s;

    &.active   { background: $hero; }
    &.inactive { background: $line-2; }
    &:disabled { opacity: .6; cursor: default; }
    &:focus-visible { outline: 2px solid $brown; outline-offset: 2px; }

    .toggle-knob {
        position: absolute;
        top: 3px;
        left: 3px;
        width: 20px;
        height: 20px;
        border-radius: 10px;
        background: $white;
        box-shadow: 0 1px 2px rgba(74, 40, 20, .25);
        transition: transform .15s;
    }
    &.active .toggle-knob { transform: translateX(18px); }
}

/* ── 로딩 / 빈 상태 ── */
.loader-rows { display: flex; flex-direction: column; margin-top: 18px; border-top: 1px solid $line; }
.skeleton-row { height: 76px; border-bottom: 1px solid $line; background: rgba(239, 226, 188, .3); animation: pulse 1.6s infinite ease-in-out; }
.empty { padding: 48px 0; text-align: center; color: $sub; font-size: 14px; }

/* ── 추가/수정 팝업: 모바일은 바텀시트 ── */
.popup-overlay {
    position: fixed;
    inset: 0;
    background: rgba(43, 29, 20, .45);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 2000;
    padding: 16px;

    @media (max-width: 600px) { align-items: flex-end; padding: 0; }
}

.popup-panel {
    background: $white;
    border-radius: 16px;
    width: 100%;
    max-width: 560px;
    max-height: 90vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    box-shadow: 0 12px 40px rgba(74, 40, 20, .2);

    @media (max-width: 600px) {
        max-width: none;
        max-height: 88vh;
        border-radius: 16px 16px 0 0;
        padding-bottom: env(safe-area-inset-bottom, 0px);
    }
}

.popup-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px 20px 12px;
    border-bottom: 1px solid $line;

    h3 { margin: 0; font-size: 17px; font-weight: 700; color: $ink; }

    .btn-close {
        border: none;
        background: none;
        cursor: pointer;
        color: $sub-2;
        padding: 6px;
        display: flex;
        align-items: center;
        &:hover { color: $ink; }
    }
}

.popup-body {
    padding: 16px 20px 20px;
    overflow-y: auto;
    overflow-x: hidden;   // 입력칸이 넘쳐도 가로로 밀리지 않게
    flex: 1;
}

.form-grid {
    display: grid;
    // minmax(0, …) 이 핵심 — 1fr 은 입력칸의 최소 폭 아래로 못 줄어 좁은 화면에서 팝업 밖으로 넘친다
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
    gap: 14px 12px;

    @media (max-width: 480px) { grid-template-columns: minmax(0, 1fr); }

    .form-field {
        display: flex;
        flex-direction: column;
        gap: 5px;
        min-width: 0;

        &.full { grid-column: 1 / -1; }

        label { font-size: 13px; font-weight: 600; color: #4A3628; }
        .req { color: $red; margin-left: 2px; }

        input:not([type="radio"]) {
            width: 100%;
            min-width: 0;
            box-sizing: border-box;
            min-height: 42px;
            padding: 0 12px;
            border: 1px solid $line-2;
            border-radius: 10px;
            font-size: 16px;   // iOS 포커스 확대 방지
            color: $ink;
            font-family: inherit;
            background: $white;
            outline: none;
            transition: border-color .15s;

            &:focus { border-color: $brown; }
            &:disabled { background: #FFFDF5; color: $sub-2; }
            &::placeholder { color: #9A8C7E; }
        }

        .radio-group { display: flex; flex-wrap: wrap; gap: 6px 16px; padding: 6px 0 2px; }

        .radio-label {
            display: flex;
            align-items: center;
            gap: 6px;
            min-height: 32px;
            font-size: 14px;
            font-weight: 500;
            color: #4A3628;
            cursor: pointer;

            input[type="radio"] { cursor: pointer; accent-color: $hero; }
        }
    }
}

.popup-footer {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    padding: 12px 20px 16px;
    border-top: 1px solid $line;

    .btn-cancel,
    .btn-save {
        min-height: 42px;
        padding: 0 18px;
        border-radius: 10px;
        font-size: 15px;
        font-weight: 600;
        font-family: inherit;
        cursor: pointer;
    }
    .btn-cancel { border: 1px solid $line-2; background: $white; color: #4A3628; }
    .btn-save {
        border: none;
        background: $hero;
        color: $cream;
        font-weight: 700;
        &:hover { background: $brown; }
        &:disabled { opacity: .55; cursor: not-allowed; }
    }
}

/* ── Transition ── */
.fade-enter-active,
.fade-leave-active { transition: opacity .18s; }
.fade-enter-from,
.fade-leave-to { opacity: 0; }

@keyframes pulse {
    0%, 100% { opacity: .5; }
    50%      { opacity: .9; }
}
</style>
