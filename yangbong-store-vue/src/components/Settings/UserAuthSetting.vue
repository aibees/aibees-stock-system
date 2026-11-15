<template>
    <div id="user-auth-setting">
        <Headers :prop_title="title" />

        <div class="contents">
            <section class="head-desc">
                <h2>사용자 권한 부여</h2>
                <p class="desc">칩을 누르면 해당 권한이 즉시 부여/회수됩니다. 대상 사용자는 다시 로그인하거나 새로고침하면 반영됩니다.</p>
            </section>

            <div class="search">
                <input v-model="keyword" placeholder="이름 또는 이메일 검색" @keyup.enter="load" />
                <button class="btn" @click="load">검색</button>
            </div>

            <div v-if="isLoading" class="loading">불러오는 중…</div>

            <ul v-else class="user-list">
                <li v-for="u in users" :key="u.user_id" class="user-row">
                    <div class="who">
                        <span class="name">{{ u.user_name }}</span>
                        <span class="meta">#{{ u.user_id }} · {{ u.email || '-' }}</span>
                    </div>
                    <div class="roles">
                        <button v-for="r in roles" :key="r.auth_id"
                            :class="['chip', { on: u.auth_ids.includes(r.auth_id) }]"
                            :disabled="busy === key(u, r)"
                            :title="r.auth_id"
                            @click="toggle(u, r)">
                            {{ r.auth_nm }}
                        </button>
                    </div>
                </li>
                <li v-if="!users.length" class="empty">사용자가 없습니다.</li>
            </ul>
        </div>
    </div>
</template>

<script setup>
import aibeesApi from '@scripts/aibeesApi.js';

const title = ref('사용자 권한');

const keyword   = ref('');
const users     = ref([]);
const roles     = ref([]);
const isLoading = ref(false);
const busy      = ref('');

const key = (u, r) => `${u.user_id}:${r.auth_id}`;

const load = async () => {
    isLoading.value = true;
    try {
        const { data } = await aibeesApi.get('/api/v1/master/admin/users', {
            params: { keyword: keyword.value.trim() }
        });
        users.value = data.data?.users ?? [];
        roles.value = data.data?.roles ?? [];
    } finally {
        isLoading.value = false;
    }
};

const toggle = async (u, r) => {
    const had = u.auth_ids.includes(r.auth_id);
    busy.value = key(u, r);
    try {
        await aibeesApi.put(`/api/v1/master/admin/users/${u.user_id}/roles/${r.auth_id}`, { enabled: !had });
        u.auth_ids = had ? u.auth_ids.filter(a => a !== r.auth_id) : [...u.auth_ids, r.auth_id];
    } catch (e) {
        alert(e?.response?.data?.error?.message ?? '권한 변경에 실패했습니다.');
    } finally {
        busy.value = '';
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

#user-auth-setting {
    min-height: 100vh;
    background: $gray-50;
    color: $gray-900;
    font-family: 'Pretendard', -apple-system, sans-serif;
}
.contents { max-width: 900px; margin: 0 auto; padding: 28px 16px 100px; }
.head-desc h2 { margin: 0 0 6px; text-align: left; }
.desc { color: $gray-500; font-size: 13px; margin: 0 0 16px; line-height: 1.5; text-align: left; }
.loading, .empty { padding: 40px; text-align: center; color: $gray-400; }

.search { display: flex; gap: 8px; margin-bottom: 16px;
    input { flex: 1; padding: 8px 10px; border: 1px solid $gray-200; border-radius: 6px; font-size: 14px; }
    .btn { padding: 8px 16px; border: 0; border-radius: 6px; background: $gray-900; color: #fff; cursor: pointer; } }

.user-list { list-style: none; margin: 0; padding: 0; background: #fff; border: 1px solid $gray-200; border-radius: 10px; }
.user-row { display: flex; flex-wrap: wrap; gap: 10px 16px; align-items: center; justify-content: space-between;
    padding: 12px 16px; border-top: 1px solid $gray-100; text-align: left;
    &:first-child { border-top: 0; } }
.who { display: flex; flex-direction: column; gap: 2px;
    .name { font-weight: 600; font-size: 14px; }
    .meta { font-size: 12px; color: $gray-400; } }
.roles { display: flex; flex-wrap: wrap; gap: 6px; }
.chip { padding: 5px 12px; border: 1px solid $gray-200; border-radius: 14px; background: #fff; color: $gray-500; font-size: 12px; cursor: pointer;
    &.on { background: $gray-900; border-color: $gray-900; color: #fff; }
    &:disabled { opacity: .5; cursor: default; } }
</style>
