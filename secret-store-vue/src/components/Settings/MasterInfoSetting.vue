<template>
    <div id="master-info-setting">
        <Headers :prop_title="title" />

        <div class="contents">
            <section class="head-desc">
                <h2>연동 키 관리</h2>
                <p class="desc">master_infos 에 저장된 외부 연동 키(KIS 토큰, 네이버/구글 OAuth 등)입니다.
                    값은 서버가 바로 읽으므로 수정 즉시 반영됩니다. 키 이름(key_type)은 전체에서 하나여야 합니다.</p>
            </section>

            <div class="toolbar">
                <input v-model="keyword" placeholder="분류 또는 키 이름 검색" />
                <button class="btn" @click="openNew">새 키</button>
            </div>

            <!-- 등록/수정 폼: 새 키이거나 목록에서 고른 행 -->
            <form v-if="form" class="edit-form" @submit.prevent="save">
                <label>분류(category)
                    <input v-model="form.category" maxlength="45" required placeholder="예: GOOGLE_AUTH" />
                </label>
                <label>키 이름(key_type)
                    <input v-model="form.key_type" maxlength="20" required :disabled="!form.isNew"
                        placeholder="예: GOOGLE_IOS_ID" />
                </label>
                <label>값(key_value)
                    <textarea v-model="form.key_value" maxlength="350" rows="3" required></textarea>
                </label>
                <label>만료일시(expired_date)
                    <input v-model="form.expired_date" placeholder="2999-12-31 23:59:59" />
                </label>
                <div class="form-actions">
                    <button type="button" v-if="!form.isNew" class="btn-text danger" :disabled="busy" @click="remove">삭제</button>
                    <span class="spacer"></span>
                    <button type="button" class="btn-text" :disabled="busy" @click="form = null">취소</button>
                    <button type="submit" class="btn" :disabled="busy">저장</button>
                </div>
            </form>

            <div v-if="isLoading" class="loading">불러오는 중…</div>

            <ul v-else class="key-list">
                <li v-for="r in filtered" :key="r.key_type" class="key-row"
                    :class="{ selected: form && !form.isNew && form.key_type === r.key_type }">
                    <button type="button" class="row-main" @click="openEdit(r)">
                        <span class="name">{{ r.key_type }}</span>
                        <span class="meta">{{ r.category }} · 만료 {{ fmtDate(r.expired_date) }}
                            <span v-if="isExpired(r)" class="expired">만료됨</span></span>
                        <span class="value">{{ shown[r.key_type] ? r.key_value : mask(r.key_value) }}</span>
                    </button>
                    <button type="button" class="btn-text" @click="shown[r.key_type] = !shown[r.key_type]">
                        {{ shown[r.key_type] ? '숨기기' : '보기' }}
                    </button>
                </li>
                <li v-if="!filtered.length" class="empty">키가 없습니다.</li>
            </ul>
        </div>
    </div>
</template>

<script setup>
import aibeesApi from '@scripts/aibeesApi.js';

const title = ref('연동 키');

const rows      = ref([]);
const keyword   = ref('');
const isLoading = ref(false);
const busy      = ref(false);
const form      = ref(null);      // { isNew, key_type, category, key_value, expired_date }
const shown     = reactive({});   // key_type → 값 보기 여부

const filtered = computed(() => {
    const k = keyword.value.trim().toLowerCase();
    if (!k) return rows.value;
    return rows.value.filter(r => r.key_type.toLowerCase().includes(k) || r.category.toLowerCase().includes(k));
});

// 비밀값이 섞여 있어 기본은 가린다. 앞 4자만 보여 어떤 키인지 구분만 되게 한다.
const mask = (v) => {
    const s = String(v ?? '');
    return s.length <= 4 ? '••••' : `${s.slice(0, 4)}${'•'.repeat(Math.min(s.length - 4, 12))} (${s.length}자)`;
};
const fmtDate = (v) => String(v ?? '').slice(0, 19);
const isExpired = (r) => {
    const t = new Date(String(r.expired_date).replace(' ', 'T'));
    return !Number.isNaN(t.getTime()) && t < new Date();
};

const load = async () => {
    isLoading.value = true;
    try {
        const { data } = await aibeesApi.get('/api/v1/master/admin/master-infos');
        rows.value = data.data ?? [];
    } finally {
        isLoading.value = false;
    }
};

const openNew = () => {
    form.value = { isNew: true, key_type: '', category: '', key_value: '', expired_date: '2999-12-31 23:59:59' };
};
const openEdit = (r) => {
    form.value = { isNew: false, key_type: r.key_type, category: r.category,
                   key_value: r.key_value, expired_date: fmtDate(r.expired_date) };
};

const errMsg = (e, fallback) => e?.response?.data?.error?.message ?? fallback;

const save = async () => {
    const f = form.value;
    const keyType = f.key_type.trim();
    if (f.isNew && rows.value.some(r => r.key_type === keyType)
        && !confirm(`${keyType} 는 이미 있습니다. 덮어쓸까요?`)) return;
    busy.value = true;
    try {
        await aibeesApi.put(`/api/v1/master/admin/master-infos/${encodeURIComponent(keyType)}`, {
            key_value: f.key_value, category: f.category.trim(), expired_date: f.expired_date.trim(),
        });
        form.value = null;
        await load();
    } catch (e) {
        alert(errMsg(e, '저장에 실패했습니다.'));
    } finally {
        busy.value = false;
    }
};

const remove = async () => {
    const keyType = form.value.key_type;
    if (!confirm(`${keyType} 를 삭제할까요? 이 키를 읽는 기능(로그인·KIS 연동 등)이 바로 멈출 수 있습니다.`)) return;
    busy.value = true;
    try {
        await aibeesApi.delete(`/api/v1/master/admin/master-infos/${encodeURIComponent(keyType)}`);
        form.value = null;
        await load();
    } catch (e) {
        alert(errMsg(e, '삭제에 실패했습니다.'));
    } finally {
        busy.value = false;
    }
};

onMounted(load);
</script>

<style scoped lang="scss">
$gray-50: #fafafa;
$gray-100: #efefef;
$gray-200: #dcdcdc;
$gray-400: #9a9a9a;
$gray-500: #737373;
$gray-900: #141414;
$red: #d93025;

#master-info-setting {
    min-height: 100vh;
    background: $gray-50;
    color: $gray-900;
    font-family: 'Pretendard', -apple-system, sans-serif;
}
.contents { max-width: 900px; margin: 0 auto; padding: 28px 16px 100px; }
.head-desc h2 { margin: 0 0 6px; text-align: left; }
.desc { color: $gray-500; font-size: 13px; margin: 0 0 16px; line-height: 1.5; text-align: left; }
.loading, .empty { padding: 40px; text-align: center; color: $gray-400; }

.toolbar { display: flex; gap: 8px; margin-bottom: 16px;
    input { flex: 1; min-width: 0; padding: 8px 10px; border: 1px solid $gray-200; border-radius: 6px; font-size: 14px; } }
.btn { padding: 8px 16px; border: 0; border-radius: 6px; background: $gray-900; color: #fff; cursor: pointer; font-size: 14px;
    &:disabled { opacity: .5; cursor: default; } }
.btn-text { padding: 6px 8px; border: 0; background: none; color: $gray-500; font-size: 13px; cursor: pointer; flex-shrink: 0;
    &.danger { color: $red; }
    &:disabled { opacity: .5; cursor: default; } }

.edit-form { display: flex; flex-direction: column; gap: 12px; margin-bottom: 16px; padding: 16px;
    background: #fff; border: 1px solid $gray-200; border-radius: 10px; text-align: left;
    label { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: $gray-500; }
    input, textarea { padding: 8px 10px; border: 1px solid $gray-200; border-radius: 6px; font-size: 14px; color: $gray-900;
        font-family: inherit; word-break: break-all;
        &:disabled { background: $gray-50; color: $gray-500; } }
    textarea { resize: vertical; font-family: ui-monospace, Menlo, monospace; font-size: 13px; } }
.form-actions { display: flex; align-items: center; gap: 8px; .spacer { flex: 1; } }

.key-list { list-style: none; margin: 0; padding: 0; background: #fff; border: 1px solid $gray-200; border-radius: 10px; }
.key-row { display: flex; align-items: center; gap: 8px; padding: 12px 16px; border-top: 1px solid $gray-100;
    &:first-child { border-top: 0; }
    &.selected { background: $gray-50; } }
.row-main { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; padding: 0; border: 0;
    background: none; text-align: left; cursor: pointer; color: inherit;
    .name { font-weight: 600; font-size: 14px; }
    .meta { font-size: 12px; color: $gray-400; }
    .expired { color: $red; margin-left: 4px; }
    .value { font-size: 12px; color: $gray-500; font-family: ui-monospace, Menlo, monospace; word-break: break-all; } }
</style>
