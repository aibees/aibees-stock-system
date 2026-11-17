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

#user-auth-setting {
    min-height: 100vh;
    background: var(--sc-bg);
    color: var(--sc-text);
    font-family: 'Pretendard', -apple-system, sans-serif;
}
.contents { max-width: 900px; margin: 0 auto; padding: 28px 16px 100px; }
.head-desc h2 { margin: 0 0 6px; text-align: left; }
.desc { color: var(--sc-text-sub); font-size: 13px; margin: 0 0 16px; line-height: 1.5; text-align: left; }
.loading, .empty { padding: 40px; text-align: center; color: var(--sc-text-mute); }

.search { display: flex; gap: 8px; margin-bottom: 16px;
    input { flex: 1; padding: 8px 10px; border: 1px solid var(--sc-border); border-radius: 6px; font-size: 14px; }
    .btn { padding: 8px 16px; border: 0; border-radius: 6px; background: var(--sc-strong-bg); color: var(--sc-strong-text); cursor: pointer; } }

.user-list { list-style: none; margin: 0; padding: 0; background: var(--sc-surface); border: 1px solid var(--sc-border); border-radius: 10px; }
.user-row { display: flex; flex-wrap: wrap; gap: 10px 16px; align-items: center; justify-content: space-between;
    padding: 12px 16px; border-top: 1px solid var(--sc-border); text-align: left;
    &:first-child { border-top: 0; } }
.who { display: flex; flex-direction: column; gap: 2px;
    .name { font-weight: 600; font-size: 14px; }
    .meta { font-size: 12px; color: var(--sc-text-mute); } }
.roles { display: flex; flex-wrap: wrap; gap: 6px; }
.chip { padding: 5px 12px; border: 1px solid var(--sc-border); border-radius: 14px; background: var(--sc-surface); color: var(--sc-text-sub); font-size: 12px; cursor: pointer;
    &.on { background: var(--sc-point); border-color: var(--sc-point); color: var(--sc-on-point); }
    &:disabled { opacity: .5; cursor: default; } }
</style>
