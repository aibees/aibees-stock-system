<template>
    <div id="access-log-setting">
        <BrandHeader :title="title" back="/menu" />

        <div class="contents">

            <!-- ── 상단 타이틀 ── -->
            <section class="head-desc">
                <div class="head-right">
                    <button class="btn-refresh" @click="reloadCurrent">
                        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none"
                            stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M23 4v6h-6" />
                            <path d="M1 20v-6h6" />
                            <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10" />
                            <path d="M20.49 15a9 9 0 0 1-14.85 3.36L1 14" />
                        </svg>
                        새로고침
                    </button>
                </div>
            </section>

            <!-- ── 탭 ── -->
            <nav class="tab-nav">
                <button v-for="t in tabs" :key="t.key" :class="['tab-btn', { active: activeTab === t.key }]"
                    @click="switchTab(t.key)">
                    {{ t.label }}
                </button>
            </nav>

            <!-- ══ 탭1: 로그인/로그아웃 (user_login_log) ══ -->
            <div v-show="activeTab === 'login'">
                <section class="filter-bar">
                    <div class="filter-group">
                        <span class="filter-label">유형</span>
                        <div class="chip-group">
                            <button v-for="o in loginTypeOptions" :key="o.value"
                                :class="['filter-chip', { active: loginFilter.loginType === o.value }]"
                                @click="setLoginFilter('loginType', o.value)">{{ o.label }}</button>
                        </div>
                    </div>
                    <div class="filter-group">
                        <span class="filter-label">결과</span>
                        <div class="chip-group">
                            <button v-for="o in resultOptions" :key="o.value"
                                :class="['filter-chip', { active: loginFilter.result === o.value }]"
                                @click="setLoginFilter('result', o.value)">{{ o.label }}</button>
                        </div>
                    </div>
                    <div class="filter-group">
                        <span class="filter-label">검색</span>
                        <input class="filter-input" v-model.trim="loginFilter.keyword" placeholder="이메일/이름/IP"
                            @keyup.enter="applyLoginFilter" />
                    </div>
                    <div class="filter-group">
                        <span class="filter-label">기간</span>
                        <input class="filter-input date" type="date" v-model="loginFilter.from" />
                        <span class="tilde">~</span>
                        <input class="filter-input date" type="date" v-model="loginFilter.to" />
                    </div>
                    <button class="btn-apply" @click="applyLoginFilter">조회</button>
                </section>

                <section class="table-section">
                    <div v-if="login.loading" class="loader-rows">
                        <div v-for="n in 6" :key="n" class="skeleton-row"></div>
                    </div>
                    <table v-else class="log-table">
                        <thead>
                            <tr>
                                <th class="col-time">시각</th>
                                <th class="col-user">사용자</th>
                                <th class="col-type">유형</th>
                                <th class="col-status">결과</th>
                                <th class="col-desc">상세</th>
                                <th class="col-ip">IP</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr v-for="row in login.list" :key="row.log_id">
                                <td class="col-time">{{ formatDateTime(row.created_date) }}</td>
                                <td class="col-user">{{ userLabel(row) }}</td>
                                <td class="col-type">{{ loginTypeLabel(row.login_type) }}</td>
                                <td class="col-status">
                                    <span :class="['status-badge', resultClass(row.result)]">{{ resultLabel(row.result) }}</span>
                                </td>
                                <td class="col-desc">{{ row.fail_reason ?? row.login_key ?? '-' }}</td>
                                <td class="col-ip">{{ row.client_ip ?? '-' }}</td>
                            </tr>
                            <tr v-if="!login.loading && login.list.length === 0">
                                <td colspan="6" class="empty-cell">조회된 로그인 기록이 없습니다.</td>
                            </tr>
                        </tbody>
                    </table>
                </section>

                <section class="mobile-list">
                    <div v-if="login.loading" class="loader-rows">
                        <div v-for="n in 4" :key="n" class="skeleton-row"></div>
                    </div>
                    <ul v-else class="log-ul">
                        <li v-for="row in login.list" :key="row.log_id" class="log-li">
                            <div class="li-top">
                                <span class="li-time">{{ formatDateTime(row.created_date) }}</span>
                                <span :class="['status-badge', resultClass(row.result)]">{{ resultLabel(row.result) }}</span>
                            </div>
                            <div class="li-name">{{ userLabel(row) }} · {{ loginTypeLabel(row.login_type) }}</div>
                            <div class="li-row" v-if="row.fail_reason ?? row.login_key">
                                <span class="li-label">상세</span>
                                <span>{{ row.fail_reason ?? row.login_key }}</span>
                            </div>
                            <div class="li-row">
                                <span class="li-label">IP</span>
                                <span>{{ row.client_ip ?? '-' }}</span>
                            </div>
                        </li>
                        <li v-if="login.list.length === 0" class="empty-cell">조회된 로그인 기록이 없습니다.</li>
                    </ul>
                </section>

                <section class="pagination" v-if="!login.loading && login.totalPages > 0">
                    <button class="page-btn" @click="goLoginPage(0)" :disabled="login.page === 0">처음</button>
                    <button class="page-btn" @click="goLoginPage(login.page - 1)" :disabled="login.page === 0">이전</button>
                    <span class="page-info">{{ login.page + 1 }} / {{ login.totalPages }}</span>
                    <button class="page-btn" @click="goLoginPage(login.page + 1)" :disabled="login.page >= login.totalPages - 1">다음</button>
                    <button class="page-btn" @click="goLoginPage(login.totalPages - 1)" :disabled="login.page >= login.totalPages - 1">마지막</button>
                </section>
            </div>

            <!-- ══ 탭2: 메뉴(화면) 접근 (user_menu_access_log) ══ -->
            <div v-show="activeTab === 'menu'">
                <section class="filter-bar">
                    <div class="filter-group">
                        <span class="filter-label">메뉴코드</span>
                        <input class="filter-input" v-model.trim="menuFilter.menuCode" placeholder="예) StockSector"
                            @keyup.enter="applyMenuFilter" />
                    </div>
                    <div class="filter-group">
                        <span class="filter-label">검색</span>
                        <input class="filter-input" v-model.trim="menuFilter.keyword" placeholder="이름/이메일/IP/경로"
                            @keyup.enter="applyMenuFilter" />
                    </div>
                    <div class="filter-group">
                        <span class="filter-label">기간</span>
                        <input class="filter-input date" type="date" v-model="menuFilter.from" />
                        <span class="tilde">~</span>
                        <input class="filter-input date" type="date" v-model="menuFilter.to" />
                    </div>
                    <button class="btn-apply" @click="applyMenuFilter">조회</button>
                </section>

                <section class="table-section">
                    <div v-if="menu.loading" class="loader-rows">
                        <div v-for="n in 6" :key="n" class="skeleton-row"></div>
                    </div>
                    <table v-else class="log-table">
                        <thead>
                            <tr>
                                <th class="col-time">시각</th>
                                <th class="col-user">사용자</th>
                                <th class="col-code">메뉴코드</th>
                                <th class="col-path">경로</th>
                                <th class="col-ip">IP</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr v-for="row in menu.list" :key="row.log_id">
                                <td class="col-time">{{ formatDateTime(row.created_date) }}</td>
                                <td class="col-user">{{ userLabel(row) }}</td>
                                <td class="col-code"><span class="code-chip">{{ row.menu_code ?? '-' }}</span></td>
                                <td class="col-path">{{ row.menu_path }}</td>
                                <td class="col-ip">{{ row.client_ip ?? '-' }}</td>
                            </tr>
                            <tr v-if="!menu.loading && menu.list.length === 0">
                                <td colspan="5" class="empty-cell">조회된 접근 기록이 없습니다.</td>
                            </tr>
                        </tbody>
                    </table>
                </section>

                <section class="mobile-list">
                    <div v-if="menu.loading" class="loader-rows">
                        <div v-for="n in 4" :key="n" class="skeleton-row"></div>
                    </div>
                    <ul v-else class="log-ul">
                        <li v-for="row in menu.list" :key="row.log_id" class="log-li">
                            <div class="li-top">
                                <span class="li-time">{{ formatDateTime(row.created_date) }}</span>
                                <span class="code-chip">{{ row.menu_code ?? '-' }}</span>
                            </div>
                            <div class="li-name">{{ userLabel(row) }}</div>
                            <div class="li-row">
                                <span class="li-label">경로</span>
                                <span>{{ row.menu_path }}</span>
                            </div>
                            <div class="li-row">
                                <span class="li-label">IP</span>
                                <span>{{ row.client_ip ?? '-' }}</span>
                            </div>
                        </li>
                        <li v-if="menu.list.length === 0" class="empty-cell">조회된 접근 기록이 없습니다.</li>
                    </ul>
                </section>

                <section class="pagination" v-if="!menu.loading && menu.totalPages > 0">
                    <button class="page-btn" @click="goMenuPage(0)" :disabled="menu.page === 0">처음</button>
                    <button class="page-btn" @click="goMenuPage(menu.page - 1)" :disabled="menu.page === 0">이전</button>
                    <span class="page-info">{{ menu.page + 1 }} / {{ menu.totalPages }}</span>
                    <button class="page-btn" @click="goMenuPage(menu.page + 1)" :disabled="menu.page >= menu.totalPages - 1">다음</button>
                    <button class="page-btn" @click="goMenuPage(menu.totalPages - 1)" :disabled="menu.page >= menu.totalPages - 1">마지막</button>
                </section>
            </div>
        </div>
    </div>
</template>

<script setup>
import aibeesApi from '@scripts/aibeesApi.js';

const title = ref('접속 로그');

const tabs = [
    { key: 'login', label: '로그인/로그아웃' },
    { key: 'menu', label: '메뉴 접근' },
];
const activeTab = ref('login');
const loaded = reactive({ login: false, menu: false });

const SIZE = 20;
const makeState = () => reactive({ list: [], loading: true, page: 0, size: SIZE, totalPages: 0 });
const login = makeState();
const menu = makeState();

/* ── 필터 옵션/상태 ── */
const loginTypeOptions = [
    { value: '', label: '전체' },
    { value: 'EMAIL', label: '이메일' },
    { value: 'NAVER', label: '네이버' },
    { value: 'NAVER_CONSENT', label: '네이버 동의' },
    { value: 'GOOGLE', label: '구글' },
    { value: 'GOOGLE_CONSENT', label: '구글 동의' },
    { value: 'SIGNUP', label: '가입' },
    { value: 'LOGOUT', label: '로그아웃' },
];
const resultOptions = [
    { value: '', label: '전체' },
    { value: 'SUCCESS', label: '성공' },
    { value: 'FAIL', label: '실패' },
    { value: 'CONSENT_REQUIRED', label: '동의대기' },
    { value: 'RESET_REQUIRED', label: '재설정필요' },
];

const loginFilter = reactive({ loginType: '', result: '', keyword: '', from: '', to: '' });
const menuFilter = reactive({ menuCode: '', keyword: '', from: '', to: '' });

/* ── fetch: 로그인/로그아웃 ── */
const fetchLoginList = async () => {
    login.loading = true;
    try {
        const params = { page: login.page, size: login.size };
        if (loginFilter.loginType) params.loginType = loginFilter.loginType;
        if (loginFilter.result) params.result = loginFilter.result;
        if (loginFilter.keyword) params.keyword = loginFilter.keyword;
        if (loginFilter.from) params.from = loginFilter.from;
        if (loginFilter.to) params.to = loginFilter.to;
        const { data } = await aibeesApi.get('/api/v1/access-logs/login', { params });
        login.list = data.data ?? [];
        login.totalPages = data.totalPages ?? 0;
    } finally {
        login.loading = false;
    }
};

/* ── fetch: 메뉴 접근 ── */
const fetchMenuList = async () => {
    menu.loading = true;
    try {
        const params = { page: menu.page, size: menu.size };
        if (menuFilter.menuCode) params.menuCode = menuFilter.menuCode;
        if (menuFilter.keyword) params.keyword = menuFilter.keyword;
        if (menuFilter.from) params.from = menuFilter.from;
        if (menuFilter.to) params.to = menuFilter.to;
        const { data } = await aibeesApi.get('/api/v1/access-logs/menu', { params });
        menu.list = data.data ?? [];
        menu.totalPages = data.totalPages ?? 0;
    } finally {
        menu.loading = false;
    }
};

/* ── 탭 전환(지연 로딩) ── */
const loaderMap = { login: fetchLoginList, menu: fetchMenuList };
const switchTab = (key) => {
    activeTab.value = key;
    if (!loaded[key]) { loaded[key] = true; loaderMap[key](); }
};
const reloadCurrent = () => loaderMap[activeTab.value]();

/* ── 필터 적용(페이지 리셋) ── */
const applyLoginFilter = () => { login.page = 0; fetchLoginList(); };
const setLoginFilter = (k, v) => { if (loginFilter[k] === v) return; loginFilter[k] = v; login.page = 0; fetchLoginList(); };
const applyMenuFilter = () => { menu.page = 0; fetchMenuList(); };

/* ── 페이지 이동 ── */
const goLoginPage = (target) => { if (target < 0 || target > login.totalPages - 1) return; login.page = target; fetchLoginList(); };
const goMenuPage = (target) => { if (target < 0 || target > menu.totalPages - 1) return; menu.page = target; fetchMenuList(); };

/* ── 포맷/배지 헬퍼 ── */
const userLabel = (row) => row.user_name ? `${row.user_name}${row.email ? ` (${row.email})` : ''}` : (row.user_id ? `#${row.user_id}` : '-');
const loginTypeLabel = (t) => loginTypeOptions.find(o => o.value === t)?.label ?? (t ?? '-');
const resultLabel = (r) => resultOptions.find(o => o.value === r)?.label ?? (r ?? '-');
const resultClass = (r) => {
    switch (r) {
        case 'SUCCESS': return 'success';
        case 'FAIL': return 'fail';
        case 'CONSENT_REQUIRED':
        case 'RESET_REQUIRED': return 'running';
        default: return 'default';
    }
};
const formatDateTime = (v) => v ? String(v).replace('T', ' ').replace(/\.\d+Z?$/, '').slice(0, 19) : '-';

onMounted(() => { loaded.login = true; fetchLoginList(); });
</script>

<style scoped lang="scss">
$white: #ffffff;
$gray-50: #fafafa;
$gray-100: #efefef;
$gray-200: #dcdcdc;
$gray-300: #c4c4c4;
$gray-400: #9a9a9a;
$gray-500: #737373;
$gray-700: #3d3d3d;
$gray-900: #141414;
$navy: #141414;

#access-log-setting {
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
    justify-content: flex-end;
    margin-bottom: 12px;
}

.btn-refresh {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 8px 16px;
    background: $navy;
    color: $white;
    border: none;
    border-radius: 0;
    font-size: 0.84rem;
    font-weight: 600;
    cursor: pointer;
    font-family: inherit;
    transition: background .15s;

    &:hover {
        background: #000000;
    }
}

/* ── Tabs ── */
.tab-nav {
    display: flex;
    gap: 4px;
    border-bottom: 1px solid $gray-200;
    margin-bottom: 16px;
}

.tab-btn {
    padding: 9px 18px;
    border: none;
    background: none;
    color: $gray-500;
    font-size: 0.86rem;
    font-weight: 600;
    cursor: pointer;
    font-family: inherit;
    border-bottom: 2px solid transparent;
    margin-bottom: -1px;
    transition: color .12s, border-color .12s;

    &:hover {
        color: $gray-700;
    }

    &.active {
        color: $navy;
        border-bottom-color: $navy;
    }
}

/* ── Filter bar ── */
.filter-bar {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 18px;
    margin-bottom: 16px;
    padding: 14px 16px;
    background: $white;
    border: 1px solid $gray-200;
}

.filter-group {
    display: flex;
    align-items: center;
    gap: 10px;
}

.filter-label {
    font-size: 0.76rem;
    font-weight: 700;
    color: $gray-500;
    letter-spacing: .03em;
}

.chip-group {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
}

.filter-chip {
    padding: 5px 13px;
    border: 1px solid $gray-200;
    border-radius: 0;
    background: $white;
    color: $gray-700;
    font-size: 0.78rem;
    font-weight: 600;
    cursor: pointer;
    font-family: inherit;
    transition: all .12s;

    &:hover {
        border-color: $gray-900;
        color: $gray-900;
    }

    &.active {
        background: $navy;
        border-color: $navy;
        color: $white;
    }
}

.filter-input {
    padding: 6px 10px;
    border: 1px solid $gray-200;
    border-radius: 0;
    font-size: 0.8rem;
    color: $gray-900;
    font-family: inherit;
    outline: none;
    transition: border-color .15s;

    &:focus {
        border-color: $gray-900;
    }

    &.date {
        padding: 5px 8px;
    }
}

.tilde {
    color: $gray-400;
}

.btn-apply {
    padding: 7px 18px;
    border: none;
    background: $navy;
    color: $white;
    border-radius: 0;
    font-size: 0.82rem;
    font-weight: 700;
    cursor: pointer;
    font-family: inherit;
    transition: background .15s;

    &:hover {
        background: #000000;
    }
}

/* ── Table (Desktop) ── */
.table-section {
    background: $white;
    border: 1px solid $gray-200;
    border-radius: 0;
    overflow: hidden;
    overflow-x: auto;

    @media (max-width: 860px) {
        display: none;
    }
}

.log-table {
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
        white-space: nowrap;
    }

    tbody tr:last-child td {
        border-bottom: none;
    }

    tbody tr:hover td {
        background: $gray-50;
    }
}

.col-time { width: 150px; color: $gray-500; font-size: 0.78rem; }
.col-user { min-width: 160px; }
.col-type { width: 110px; }
.col-status { width: 100px; text-align: center; }
.col-desc { min-width: 220px; white-space: normal !important; color: $gray-500; }
.col-ip { width: 130px; font-family: 'SFMono-Regular', Consolas, monospace; font-size: 0.78rem; }
.col-code { width: 140px; }
.col-path { min-width: 180px; font-family: 'SFMono-Regular', Consolas, monospace; font-size: 0.78rem; }

.code-chip {
    font-size: 0.72rem;
    font-weight: 600;
    background: $gray-100;
    color: $gray-700;
    padding: 2px 7px;
    border-radius: 0;
    border: 1px solid $gray-200;
}

/* status badge */
.status-badge {
    font-size: 0.7rem;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 0;
    white-space: nowrap;

    &.success {
        background: $white;
        color: $gray-500;
        border: 1px solid $gray-200;
    }

    &.fail {
        background: $gray-900;
        color: $white;
        border: 1px solid $gray-900;
    }

    &.running {
        background: $gray-100;
        color: $gray-900;
        border: 1px solid $gray-400;
    }

    &.default {
        background: $gray-100;
        color: $gray-500;
        border: 1px solid $gray-200;
    }
}

/* skeleton */
.loader-rows {
    padding: 8px;
}

.skeleton-row {
    height: 42px;
    background: $gray-100;
    border-radius: 0;
    margin-bottom: 6px;
    animation: pulse 1.6s infinite ease-in-out;
}

.empty-cell {
    text-align: center;
    padding: 60px 0;
    color: $gray-400;
    font-size: 0.88rem;
}

/* ── Mobile List (ul/li) ── */
.mobile-list {
    display: none;

    @media (max-width: 860px) {
        display: block;
    }
}

.log-ul {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 10px;
}

.log-li {
    background: $white;
    border: 1px solid $gray-200;
    border-radius: 0;
    padding: 14px;
}

.li-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
}

.li-time {
    font-size: 0.76rem;
    color: $gray-500;
    font-variant-numeric: tabular-nums;
}

.li-name {
    font-size: 0.9rem;
    font-weight: 700;
    color: $gray-900;
    margin-bottom: 8px;
}

.li-row {
    display: flex;
    gap: 8px;
    align-items: flex-start;
    font-size: 0.8rem;
    margin-bottom: 4px;
    color: $gray-700;

    .li-label {
        flex-shrink: 0;
        width: 56px;
        color: $gray-500;
        font-weight: 600;
    }
}

/* ── Pagination ── */
.pagination {
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 8px;
    margin-top: 18px;
}

.page-btn {
    padding: 6px 14px;
    border: 1px solid $gray-200;
    border-radius: 0;
    background: $white;
    color: $gray-700;
    font-size: 0.8rem;
    font-weight: 600;
    cursor: pointer;
    font-family: inherit;
    transition: border-color .12s, color .12s;

    &:hover:not(:disabled) {
        border-color: $navy;
        color: $navy;
    }

    &:disabled {
        opacity: .45;
        cursor: not-allowed;
    }
}

.page-info {
    font-size: 0.82rem;
    font-weight: 600;
    color: $gray-700;
    padding: 0 6px;
}

@keyframes pulse {

    0%,
    100% {
        opacity: .5;
    }

    50% {
        opacity: .9;
    }
}
</style>
