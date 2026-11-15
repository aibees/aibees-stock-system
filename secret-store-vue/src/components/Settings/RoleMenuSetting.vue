<template>
    <div id="role-menu-setting">
        <BrandHeader :title="title" back="/menu" />

        <!-- ── 권한 선택: 화면 폭을 꽉 채우는 탭 바(많으면 가로 스크롤) ── -->
        <nav class="role-tabs" role="tablist" aria-label="권한">
            <button v-for="r in roles" :key="r.auth_id" type="button" role="tab"
                :class="['role-tab', { on: r.auth_id === selected && !creating }]"
                :aria-selected="r.auth_id === selected && !creating ? 'true' : 'false'"
                @click="selectRole(r.auth_id)">
                {{ r.auth_nm }}<em>{{ r.user_count ?? 0 }}</em>
            </button>
        </nav>

        <div class="contents">
            <!-- ── 권한 생성: 폭 전체 버튼 → 폭 전체 폼 ── -->
            <button v-if="!creating" type="button" class="new-role" @click="startCreate">+ 새 권한 만들기</button>

            <section v-else class="sec">
                <h2 class="sec-title">새 권한</h2>
                <div class="field">
                    <label for="new-auth-id">권한 ID</label>
                    <input id="new-auth-id" v-model="newRole.auth_id" placeholder="TRADE_USER" maxlength="64"
                        autocapitalize="characters" @input="newRole.auth_id = newRole.auth_id.toUpperCase()" />
                </div>
                <div class="field">
                    <label for="new-auth-nm">권한 이름</label>
                    <input id="new-auth-nm" v-model="newRole.auth_nm" placeholder="자동매매 사용자" maxlength="200"
                        @keyup.enter="createRole" />
                </div>
                <div class="row-actions">
                    <button type="button" class="btn-ghost" @click="creating = false">취소</button>
                    <button type="button" class="btn-primary" :disabled="!canCreate || saving" @click="createRole">
                        {{ saving ? '만드는 중…' : '만들기' }}
                    </button>
                </div>
            </section>

            <div v-if="!creating && isLoading" class="loading">불러오는 중…</div>

            <template v-else-if="!creating && selected">
                <!-- ── 권한 정보 ── -->
                <section class="sec">
                    <div class="sec-head">
                        <h2 class="sec-title">권한 정보</h2>
                        <button type="button" class="act danger" :disabled="saving" @click="deleteRole">삭제</button>
                    </div>
                    <dl class="info">
                        <div class="info-row"><dt>권한 ID</dt><dd class="mono">{{ selected }}</dd></div>
                        <div class="info-row"><dt>사용자</dt><dd>{{ selectedRole?.user_count ?? 0 }}명</dd></div>
                        <div class="info-row">
                            <dt><label for="edit-auth-nm">이름</label></dt>
                            <dd class="inline">
                                <input id="edit-auth-nm" v-model="editName" maxlength="200" @keyup.enter="saveName" />
                                <button type="button" class="btn-primary sm" :disabled="!nameDirty || saving" @click="saveName">저장</button>
                            </dd>
                        </div>
                    </dl>
                </section>

                <!-- ── 접근 메뉴 ── -->
                <section class="sec">
                    <div class="sec-head">
                        <h2 class="sec-title">접근 메뉴 <span class="count">{{ isAdminRole ? '전체' : checked.size }}</span></h2>
                        <button type="button" class="btn-primary sm" :disabled="isAdminRole || !menuDirty || saving" @click="saveMenus">
                            {{ saving ? '저장 중…' : '저장' }}
                        </button>
                    </div>

                    <div v-for="root in tree" :key="root.menu_code" class="menu-group">
                        <div class="group-head">
                            <span class="group-title">{{ root.menu_title || root.menu_name }}</span>
                            <span v-for="t in tagsOf(root)" :key="t.text" class="tag" :class="t.cls">{{ t.text }}</span>
                            <button v-if="root.children.length && !isAdminRole && selectable(root).length" type="button"
                                class="link-btn" @click="toggleGroup(root)">
                                {{ groupAllChecked(root) ? '전체 해제' : '전체 선택' }}
                            </button>
                        </div>
                        <ul v-if="root.children.length" class="menu-list">
                            <li v-for="c in root.children" :key="c.menu_code">
                                <label class="menu-row" :class="{ disabled: isFixed(c) || isAdminRole }">
                                    <input type="checkbox"
                                        :checked="isAdminRole || isFixed(c) || checked.has(c.menu_code)"
                                        :disabled="isAdminRole || isFixed(c)"
                                        @change="toggleMenu(c.menu_code)" />
                                    <span class="menu-name">{{ c.menu_title || c.menu_name }}</span>
                                    <span v-for="t in tagsOf(c)" :key="t.text" class="tag" :class="t.cls">{{ t.text }}</span>
                                </label>
                            </li>
                        </ul>
                    </div>
                </section>

                <!-- ── 기능 ── -->
                <section class="sec">
                    <div class="sec-head">
                        <h2 class="sec-title">기능</h2>
                        <button type="button" class="btn-primary sm" :disabled="!featureDirty || saving" @click="saveFeatures">
                            {{ saving ? '저장 중…' : '저장' }}
                        </button>
                    </div>
                    <div v-if="features.length" class="feature-list">
                        <span v-for="f in features" :key="f" class="feature-chip">
                            {{ f }}
                            <button type="button" class="x" :aria-label="`${f} 제거`" @click="removeFeature(f)">×</button>
                        </span>
                    </div>
                    <div class="inline">
                        <input v-model="newFeature" placeholder="AD_FREE" maxlength="64" aria-label="기능 코드"
                            @keyup.enter="addFeature" />
                        <button type="button" class="btn-ghost sm" @click="addFeature">추가</button>
                    </div>
                </section>
            </template>
        </div>
    </div>
</template>

<script setup>
import aibeesApi from '@scripts/aibeesApi.js';
import { ensureAccess } from '@scripts/useAccess.js';

const title = ref('권한별 메뉴 관리');

const roles      = ref([]);
const selected   = ref('');
const menuRoots  = ref([]);
const isLoading  = ref(false);
const saving     = ref(false);

const checked    = ref(new Set());
let   savedMenus = '';
const features   = ref([]);
let   savedFeats = '';
const newFeature = ref('');

const isAdminRole = computed(() => selected.value === 'ADMIN');
const selectedRole = computed(() => roles.value.find(r => r.auth_id === selected.value));

/* ── 권한 생성 / 이름 변경 / 삭제 ── */
const creating = ref(false);
const newRole  = ref({ auth_id: '', auth_nm: '' });
const editName = ref('');
const AUTH_ID_RE = /^[A-Z][A-Z0-9_]{1,63}$/;
const canCreate = computed(() => AUTH_ID_RE.test(newRole.value.auth_id) && newRole.value.auth_nm.trim());
const nameDirty = computed(() => editName.value.trim() && editName.value.trim() !== selectedRole.value?.auth_nm);
const deleteBlockReason = computed(() => {
    if (isAdminRole.value) return 'ADMIN 권한은 삭제할 수 없습니다.';
    const n = selectedRole.value?.user_count ?? 0;
    return n ? `이 권한을 가진 사용자가 ${n}명 있어 삭제할 수 없습니다. 사용자 권한 부여 화면에서 먼저 회수하세요.` : '';
});
const canDelete = computed(() => !deleteBlockReason.value);
const errMsg = (e, fallback) => e?.response?.data?.error?.message ?? fallback;

const reloadRoles = async () => {
    const r = await aibeesApi.get('/api/v1/master/roles');
    roles.value = r.data.data ?? [];
};

const startCreate = () => {
    if (!confirmDiscard()) return;
    newRole.value = { auth_id: '', auth_nm: '' };
    creating.value = true;
};

const createRole = async () => {
    if (!canCreate.value) return;
    saving.value = true;
    try {
        const { data } = await aibeesApi.post('/api/v1/master/roles', {
            auth_id: newRole.value.auth_id, auth_nm: newRole.value.auth_nm.trim()
        });
        await reloadRoles();
        creating.value = false;
        selected.value = '';                 // selectRole 의 "같은 권한" 가드를 피한다
        await selectRole(data.data.auth_id);
    } catch (e) {
        alert(errMsg(e, '권한을 만들지 못했습니다.'));
    } finally {
        saving.value = false;
    }
};

const saveName = async () => {
    if (!nameDirty.value) return;
    saving.value = true;
    try {
        await aibeesApi.put(`/api/v1/master/roles/${selected.value}`, { auth_nm: editName.value.trim() });
        await reloadRoles();
    } catch (e) {
        alert(errMsg(e, '이름을 바꾸지 못했습니다.'));
    } finally {
        saving.value = false;
    }
};

const deleteRole = async () => {
    // 삭제 불가 사유는 화면 문구 대신 누를 때 알려준다
    if (!canDelete.value) { alert(deleteBlockReason.value); return; }
    if (!confirm(`'${selectedRole.value?.auth_nm}'(${selected.value}) 권한을 삭제할까요? 이 권한의 메뉴·기능 설정도 함께 지워집니다.`)) return;
    saving.value = true;
    try {
        await aibeesApi.delete(`/api/v1/master/roles/${selected.value}`);
        await reloadRoles();
        selected.value = '';
        menuDirtyReset();
        const first = roles.value.find(x => x.auth_id !== 'ADMIN') ?? roles.value[0];
        if (first) await selectRole(first.auth_id);
    } catch (e) {
        alert(errMsg(e, '권한을 삭제하지 못했습니다.'));
    } finally {
        saving.value = false;
    }
};

// 부모/자식 트리(정렬). 라우트 관리와 같은 /master/menus 전체 목록을 쓴다.
const tree = computed(() =>
    [...menuRoots.value]
        .sort((a, b) => (a.sort ?? 0) - (b.sort ?? 0))
        .map(r => ({
            ...r,
            children: [...(r.children ?? [])].sort((a, b) => (a.sort ?? 0) - (b.sort ?? 0))
        }))
);

const snapshot = (arr) => JSON.stringify([...arr].sort());
const menuDirty    = computed(() => snapshot(checked.value) !== savedMenus);
const featureDirty = computed(() => snapshot(features.value) !== savedFeats);

const loadRole = async (authId) => {
    isLoading.value = true;
    try {
        const [m, f] = await Promise.all([
            aibeesApi.get(`/api/v1/master/roles/${authId}/menus`),
            aibeesApi.get(`/api/v1/master/roles/${authId}/features`)
        ]);
        checked.value  = new Set(m.data.data ?? []);
        savedMenus     = snapshot(checked.value);
        features.value = f.data.data ?? [];
        savedFeats     = snapshot(features.value);
    } finally {
        isLoading.value = false;
    }
};

const confirmDiscard = () =>
    !(menuDirty.value || featureDirty.value) || confirm('저장하지 않은 변경 사항이 있습니다. 이동할까요?');

// 삭제된 권한의 미저장 변경은 버린다(다음 권한 선택 시 "저장 안 함" 확인창이 뜨지 않게).
const menuDirtyReset = () => {
    savedMenus = snapshot(checked.value);
    savedFeats = snapshot(features.value);
};

const selectRole = async (authId) => {
    if (creating.value) {
        creating.value = false;
        if (authId === selected.value) return;
    }
    if (authId === selected.value || !confirmDiscard()) return;
    selected.value = authId;
    await loadRole(authId);
};

watch(selectedRole, (r) => { editName.value = r?.auth_nm ?? ''; }, { immediate: true });

const toggleMenu = (code) => {
    const next = new Set(checked.value);
    next.has(code) ? next.delete(code) : next.add(code);
    checked.value = next;
};

// 메뉴 상태 태그: 공개/공통은 체크 대상이 아니라는 표시, 비활성은 꺼진 메뉴
const tagsOf = (m) => {
    const tags = [];
    if (m.public_flag === 'Y') tags.push({ text: '공개', cls: 'pub' });
    else if (m.common_flag === 'Y') tags.push({ text: '공통', cls: 'com' });
    if (m.enabled_flag === 'N') tags.push({ text: '비활성', cls: 'mute' });
    return tags;
};

// 공통/공개 메뉴는 매핑 대상이 아니다(로그인 사용자 전체 / 게스트 포함 전체).
const isFixed = (m) => m.common_flag === 'Y' || m.public_flag === 'Y';
const selectable = (root) => root.children.filter(c => !isFixed(c));
const groupAllChecked = (root) => selectable(root).every(c => checked.value.has(c.menu_code));
const toggleGroup = (root) => {
    const next = new Set(checked.value);
    const all = groupAllChecked(root);
    selectable(root).forEach(c => all ? next.delete(c.menu_code) : next.add(c.menu_code));
    checked.value = next;
};

const saveMenus = async () => {
    saving.value = true;
    try {
        await aibeesApi.put(`/api/v1/master/roles/${selected.value}/menus`, { menu_codes: [...checked.value] });
        savedMenus = snapshot(checked.value);
        await ensureAccess(true); // 내 권한이 바뀌었을 수 있으니 갱신
        alert('저장되었습니다.');
    } finally {
        saving.value = false;
    }
};

const addFeature = () => {
    const code = newFeature.value.trim().toUpperCase();
    if (code && !features.value.includes(code)) features.value = [...features.value, code];
    newFeature.value = '';
};
const removeFeature = (code) => { features.value = features.value.filter(f => f !== code); };

const saveFeatures = async () => {
    saving.value = true;
    try {
        await aibeesApi.put(`/api/v1/master/roles/${selected.value}/features`, { feature_codes: features.value });
        savedFeats = snapshot(features.value);
        await ensureAccess(true);
        alert('저장되었습니다.');
    } finally {
        saving.value = false;
    }
};

onMounted(async () => {
    const [r, m] = await Promise.all([
        aibeesApi.get('/api/v1/master/roles'),
        aibeesApi.get('/api/v1/master/menus')
    ]);
    roles.value     = r.data.data ?? [];
    menuRoots.value = m.data.data ?? [];
    // 목록의 첫 권한이 ADMIN 이면 매핑이 무의미하므로 ADMIN 이 아닌 첫 권한을 우선한다.
    const first = roles.value.find(x => x.auth_id !== 'ADMIN') ?? roles.value[0];
    if (first) {
        selected.value = first.auth_id;
        await loadRole(first.auth_id);
    }
});
</script>

<style scoped lang="scss">
// 양봉상회 토큰(홈·배치·라우팅 관리와 동일). 카드 없이 흰 배경 + 구분선.
$white:   #ffffff;
$bar:     #FFF6D2;
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

#role-menu-setting {
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
    padding: 12px 16px calc(96px + env(safe-area-inset-bottom, 0px));
}
.loading { padding: 40px 0; text-align: center; color: $sub-2; font-size: 14px; }

/* ── 권한 탭 바: 화면 폭을 꽉 채운다(탭이 많으면 가로 스크롤) ── */
.role-tabs {
    display: flex;
    width: 100%;
    overflow-x: auto;
    background: $white;
    border-bottom: 1px solid $line-2;
    scrollbar-width: none;
    &::-webkit-scrollbar { display: none; }
}
.role-tab {
    flex: 1 0 auto;
    min-height: 48px;
    padding: 0 16px;
    border: 0;
    border-bottom: 3px solid transparent;
    background: transparent;
    color: $sub;
    font-size: 15px;
    font-family: inherit;
    white-space: nowrap;
    cursor: pointer;

    em { font-style: normal; font-size: 12px; color: $sub-2; margin-left: 4px; }
    &.on { color: $brown; font-weight: 700; border-bottom-color: #F6C445; em { color: $brown; } }
    &:focus-visible { outline: 2px solid $brown; outline-offset: -2px; }
}

/* ── 새 권한: 폭 전체 버튼 ── */
.new-role {
    width: 100%;
    min-height: 46px;
    margin-top: 4px;
    border: 1px dashed $line-2;
    border-radius: 10px;
    background: $white;
    color: $brown;
    font-size: 15px;
    font-weight: 600;
    font-family: inherit;
    cursor: pointer;
    &:active { background: rgba(239, 226, 188, .3); }
    &:focus-visible { outline: 2px solid $brown; outline-offset: 2px; }
}

/* ── 섹션: 위쪽 구분선 + 제목 ── */
.sec {
    padding: 16px 0 8px;
    border-top: 1px solid $line;
    margin-top: 16px;

    &:first-child { border-top: 0; margin-top: 4px; padding-top: 8px; }
}
.sec-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 8px; }
.sec-title {
    margin: 0 0 8px;
    font-size: 17px;
    font-weight: 700;
    color: $ink;
    .count { color: #A0662F; margin-left: 2px; font-size: 15px; }
}
.sec-head .sec-title { margin: 0; }

/* ── 입력 ── */
input:not([type="checkbox"]) {
    width: 100%;
    min-width: 0;
    box-sizing: border-box;
    min-height: 42px;
    padding: 0 12px;
    border: 1px solid $line-2;
    border-radius: 10px;
    background: $white;
    color: $ink;
    font-size: 16px;   // iOS 포커스 확대 방지
    font-family: inherit;
    outline: none;
    &:focus { border-color: $brown; }
    &::placeholder { color: #9A8C7E; }
}
.field { display: flex; flex-direction: column; gap: 6px; margin-bottom: 12px;
    label { font-size: 13px; font-weight: 600; color: #4A3628; } }
.inline { display: flex; gap: 8px; align-items: center; input { flex: 1; } }
.row-actions { display: flex; gap: 8px; button { flex: 1; } }

/* ── 버튼 ── */
.btn-primary,
.btn-ghost {
    min-height: 42px;
    padding: 0 16px;
    border-radius: 10px;
    font-size: 15px;
    font-weight: 600;
    font-family: inherit;
    cursor: pointer;
    white-space: nowrap;
    &.sm { min-height: 36px; padding: 0 14px; font-size: 14px; }
    &:disabled { opacity: .45; cursor: default; }
    &:focus-visible { outline: 2px solid $brown; outline-offset: 2px; }
}
.btn-primary { border: 0; background: $hero; color: $cream; }
.btn-ghost { border: 1px solid $line-2; background: $white; color: $brown; }
.act {
    min-height: 32px;
    padding: 0 8px;
    border: 0;
    border-radius: 8px;
    background: transparent;
    color: $brown;
    font-size: 14px;
    font-weight: 600;
    font-family: inherit;
    cursor: pointer;
    &.danger { color: $red; }
    &:disabled { opacity: .45; }
}
.link-btn {
    margin-left: auto;
    min-height: 32px;
    border: 0;
    background: none;
    color: $brown;
    font-size: 13px;
    font-weight: 600;
    font-family: inherit;
    cursor: pointer;
}

/* ── 권한 정보: 라벨-값 행 ── */
.info { margin: 0; }
.info-row {
    display: flex;
    align-items: center;
    gap: 12px;
    min-height: 44px;
    border-bottom: 1px solid $line;
    &:last-child { border-bottom: 0; }

    dt { flex: 0 0 64px; font-size: 14px; color: $sub; }
    dd { flex: 1; min-width: 0; margin: 0; font-size: 15px; }
    dd.inline { padding: 6px 0; }
    .mono { font-family: ui-monospace, 'SFMono-Regular', Menlo, monospace; font-size: 14px; }
}

/* ── 접근 메뉴: 그룹 제목 + 체크 목록 ── */
.menu-group { padding-top: 10px; }
.group-head {
    display: flex;
    align-items: center;
    gap: 6px;
    padding-bottom: 4px;
    border-bottom: 1px solid $line;
}
.group-title { font-size: 15px; font-weight: 700; color: $ink; }
.menu-list { margin: 0; padding: 0; list-style: none; }
.menu-row {
    display: flex;
    align-items: center;
    gap: 10px;
    min-height: 44px;
    border-bottom: 1px solid $line;
    font-size: 15px;
    cursor: pointer;

    input[type="checkbox"] { width: 18px; height: 18px; margin: 0; accent-color: $hero; flex-shrink: 0; }
    &.disabled { color: $sub-2; cursor: default; }
}
.menu-name { min-width: 0; }

.tag {
    padding: 1px 7px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 700;
    white-space: nowrap;
    &.pub  { background: #E6F3EA; color: #23784A; }
    &.com  { background: $chip; color: $brown; }
    &.mute { background: #F1ECE2; color: $sub; }
}

/* ── 기능 ── */
.feature-list { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 10px; }
.feature-chip {
    display: inline-flex;
    align-items: center;
    gap: 2px;
    padding: 2px 4px 2px 10px;
    border-radius: 999px;
    background: $chip;
    color: $brown;
    font-size: 13px;
    font-weight: 600;
    .x { min-width: 28px; min-height: 28px; border: 0; background: none; cursor: pointer; color: $brown; font-size: 16px; line-height: 1; }
}
</style>
