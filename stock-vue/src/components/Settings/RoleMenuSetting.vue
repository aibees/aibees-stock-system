<template>
    <div id="role-menu-setting">
        <Headers :prop_title="title" />

        <div class="contents">
            <section class="head-desc">
                <h2>권한별 메뉴 관리</h2>
                <p class="desc">권한(역할)마다 접근 가능한 메뉴를 지정합니다. 체크하지 않은 메뉴는 해당 권한에 노출되지 않고 직접 접근도 막힙니다.</p>
            </section>

            <!-- ── 권한 선택 ── -->
            <section class="role-tabs">
                <button v-for="r in roles" :key="r.auth_id"
                    :class="['role-tab', { active: r.auth_id === selected }]"
                    @click="selectRole(r.auth_id)">
                    <span class="role-nm">{{ r.auth_nm }}</span>
                    <span class="role-id">{{ r.auth_id }}</span>
                </button>
            </section>

            <div v-if="isLoading" class="loading">불러오는 중…</div>

            <template v-else-if="selected">
                <!-- ── 메뉴 매핑 ── -->
                <section class="panel">
                    <div class="panel-head">
                        <h3>접근 가능 메뉴</h3>
                        <button class="btn-save" :disabled="isAdminRole || !menuDirty || saving" @click="saveMenus">
                            {{ saving ? '저장 중…' : '메뉴 저장' }}
                        </button>
                    </div>
                    <p v-if="isAdminRole" class="note">ADMIN 은 모든 메뉴에 접근할 수 있어 매핑이 필요하지 않습니다.</p>

                    <ul class="tree">
                        <li v-for="root in tree" :key="root.menu_code" class="tree-root">
                            <div class="root-row">
                                <span class="root-title">{{ root.menu_title || root.menu_name }}</span>
                                <span v-if="root.public_flag === 'Y'" class="chip chip-common">공개</span>
                                <span v-else-if="root.common_flag === 'Y'" class="chip chip-common">공통</span>
                                <span v-if="root.enabled_flag === 'N'" class="chip chip-off">비활성</span>
                                <button v-if="root.children.length && !isAdminRole" class="link-btn" @click="toggleGroup(root)">
                                    {{ groupAllChecked(root) ? '전체 해제' : '전체 선택' }}
                                </button>
                            </div>
                            <ul v-if="root.children.length" class="tree-children">
                                <li v-for="c in root.children" :key="c.menu_code" class="tree-child">
                                    <label :class="{ disabled: isFixed(c) || isAdminRole }">
                                        <input type="checkbox"
                                            :checked="isAdminRole || isFixed(c) || checked.has(c.menu_code)"
                                            :disabled="isAdminRole || isFixed(c)"
                                            @change="toggleMenu(c.menu_code)" />
                                        <span>{{ c.menu_title || c.menu_name }}</span>
                                        <span class="path">{{ root.menu_path }}/{{ c.menu_path }}</span>
                                        <span v-if="c.public_flag === 'Y'" class="chip chip-common">공개</span>
                                        <span v-else-if="c.common_flag === 'Y'" class="chip chip-common">공통</span>
                                        <span v-if="c.enabled_flag === 'N'" class="chip chip-off">비활성</span>
                                    </label>
                                </li>
                            </ul>
                        </li>
                    </ul>
                </section>

                <!-- ── 기능 플래그 ── -->
                <section class="panel">
                    <div class="panel-head">
                        <h3>기능 플래그</h3>
                        <button class="btn-save" :disabled="!featureDirty || saving" @click="saveFeatures">
                            {{ saving ? '저장 중…' : '기능 저장' }}
                        </button>
                    </div>
                    <p class="note">AD_FREE: 광고를 노출하지 않음. ADMIN 도 자동 부여되지 않으며 여기서 명시한 권한에만 적용됩니다.</p>
                    <div class="feature-list">
                        <span v-for="f in features" :key="f" class="feature-chip">
                            {{ f }}
                            <button class="x" @click="removeFeature(f)" title="제거">×</button>
                        </span>
                        <span v-if="!features.length" class="empty">설정된 기능이 없습니다.</span>
                    </div>
                    <div class="feature-add">
                        <input v-model="newFeature" placeholder="예) AD_FREE" maxlength="64" @keyup.enter="addFeature" />
                        <button class="btn-add" @click="addFeature">추가</button>
                    </div>
                </section>
            </template>
        </div>
    </div>
</template>

<script setup>
import aibeesApi from '@scripts/aibeesApi.js';
import { ensureAccess } from '@scripts/useAccess.js';

const title = ref('권한별 메뉴');

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

const selectRole = async (authId) => {
    if (authId === selected.value || !confirmDiscard()) return;
    selected.value = authId;
    await loadRole(authId);
};

const toggleMenu = (code) => {
    const next = new Set(checked.value);
    next.has(code) ? next.delete(code) : next.add(code);
    checked.value = next;
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
$white: #ffffff;
$gray-50: #fafafa;
$gray-100: #efefef;
$gray-200: #dcdcdc;
$gray-400: #9a9a9a;
$gray-500: #737373;
$gray-900: #141414;

#role-menu-setting {
    min-height: 100vh;
    background: $gray-50;
    color: $gray-900;
    font-family: 'Pretendard', -apple-system, sans-serif;
}
.contents { max-width: 900px; margin: 0 auto; padding: 28px 16px 100px; }
.head-desc h2 { margin: 0 0 6px; text-align: left; }
.desc, .note { color: $gray-500; font-size: 13px; margin: 0 0 12px; line-height: 1.5; }
.loading { padding: 40px; text-align: center; color: $gray-400; }

.role-tabs { display: flex; gap: 8px; flex-wrap: wrap; margin: 16px 0; }
.role-tab {
    display: flex; flex-direction: column; align-items: flex-start; gap: 2px;
    padding: 8px 14px; border: 1px solid $gray-200; border-radius: 8px; background: $white; cursor: pointer;
    .role-nm { font-size: 14px; font-weight: 600; }
    .role-id { font-size: 11px; color: $gray-400; }
    &.active { border-color: $gray-900; background: $gray-900; color: $white; .role-id { color: #bbb; } }
}

.panel { background: $white; border: 1px solid $gray-200; border-radius: 10px; padding: 16px; margin-bottom: 16px; }
.panel-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;
    h3 { margin: 0; font-size: 15px; } }

.btn-save, .btn-add {
    padding: 7px 14px; border: 0; border-radius: 6px; background: $gray-900; color: $white;
    font-size: 13px; cursor: pointer;
    &:disabled { background: $gray-200; color: $gray-400; cursor: default; }
}

.tree { list-style: none; margin: 0; padding: 0; }
.tree-root { padding: 10px 0; border-top: 1px solid $gray-100; &:first-child { border-top: 0; } }
.root-row { display: flex; align-items: center; gap: 8px; font-weight: 600; font-size: 14px; }
.tree-children { list-style: none; margin: 6px 0 0 6px; padding: 0 0 0 14px; border-left: 2px solid $gray-100; }
.tree-child label {
    display: flex; align-items: center; gap: 8px; padding: 6px 0; font-size: 14px; cursor: pointer;
    &.disabled { color: $gray-400; cursor: default; }
    .path { font-size: 11px; color: $gray-400; }
}
.link-btn { margin-left: auto; border: 0; background: none; color: $gray-500; font-size: 12px; cursor: pointer; text-decoration: underline; }

.chip { font-size: 10px; padding: 1px 6px; border-radius: 10px; font-weight: 500; }
.chip-common { background: $gray-100; color: $gray-500; }
.chip-off { background: $gray-200; color: $gray-500; }

.feature-list { display: flex; flex-wrap: wrap; gap: 6px; margin: 8px 0 12px; }
.feature-chip { display: inline-flex; align-items: center; gap: 4px; padding: 4px 10px; background: $gray-100; border-radius: 14px; font-size: 13px;
    .x { border: 0; background: none; cursor: pointer; color: $gray-500; font-size: 14px; line-height: 1; } }
.empty { color: $gray-400; font-size: 13px; }
.feature-add { display: flex; gap: 8px;
    input { flex: 1; padding: 7px 10px; border: 1px solid $gray-200; border-radius: 6px; font-size: 13px; } }
</style>
