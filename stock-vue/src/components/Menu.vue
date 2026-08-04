<template>
    <div class="common-menu">

        <!-- ── 헤더 버튼 ── -->
        <div class="menu-header-btns">
            <button class="icon-btn" @click="goTo('/home')" title="홈으로">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"
                    fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
                    <polyline points="9 22 9 12 15 12 15 22"/>
                </svg>
                홈
            </button>
            <button class="icon-btn logout-btn" @click="handleLogout" title="로그아웃">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"
                    fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
                    <polyline points="16 17 21 12 16 7"/>
                    <line x1="21" y1="12" x2="9" y2="12"/>
                </svg>
                로그아웃
            </button>
        </div>

        <!-- ── 유저 정보 ── -->
        <div class="menu-user">
            <div class="user-avatar">{{ userInitial }}</div>
            <div class="user-info">
                <p class="user-name">{{ userName }}</p>
                <!-- <p class="user-id">{{ userId }}</p> -->
            </div>
            <div class="role-badges">
                <span v-for="r in userRoles" :key="r" class="role-badge">{{ r }}</span>
            </div>
        </div>

        <!-- ── 검색 ── -->
        <div class="menu-search-input">
            <svg class="search-icon" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24"
                fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
            </svg>
            <input v-model="searchQuery" type="text" placeholder="메뉴 검색" class="search-input" />
        </div>

        <!-- ── 메뉴 목록 ── -->
        <div class="menu-list">
            <ul class="main-ul">
                <li v-for="m in filteredMenuList" :key="m.menu_code" class="main-li">
                    <div class="main-name">{{ m.menu_name }}</div>
                    <ul class="sub-ul">
                        <li v-for="sm in m.children" :key="sm.menu_code" class="sub-li">
                            <div class="menu-link" @click="goTo(m.menu_path + '/' + sm.menu_path)">
                                <span class="link-title">{{ sm.menu_title }}</span>
                                <span class="link-sub">{{ sm.menu_name }}</span>
                            </div>
                        </li>
                    </ul>
                </li>
            </ul>
        </div>

    </div>
</template>

<script setup>
    import aibeesApi from '@scripts/aibeesApi.js';
    import { assUserSession } from '@scripts/stores/user-stores.js';

    const router    = useRouter();
    const userStore = assUserSession();

    /* ── 유저 정보 ── */
    const userName  = computed(() => userStore.getUserInfo || 'Anonymous');
    const userId    = computed(() => userStore.user.loginInfo.user_id || '');
    const userRoles = computed(() => userStore.getRole || []);
    const userInitial = computed(() => (userName.value?.[0] ?? '?').toUpperCase());

    /* ── 관리자 여부 ── */
    const isAdmin = computed(() => {
        const roles = userStore.getRole ?? [];
        return roles.some(r => {
            const v = String(r ?? '').trim();
            return v.toUpperCase() === 'ADMIN' || v.replace(/\s/g, '') === '시스템관리자';
        });
    });

    /* ── 메뉴 ── */
    const menuList    = ref([]);
    const searchQuery = ref('');

    const filteredMenuList = computed(() => {
        const q = searchQuery.value.trim().toLowerCase();

        return menuList.value
            // 1) admin_only 필터
            .filter(m => m.admin_only !== 'Y' || isAdmin.value)
            .map(m => ({
                ...m,
                children: (m.children || [])
                    .filter(sm => sm.admin_only !== 'Y' || isAdmin.value)
                    .filter(sm => !q ||
                        sm.menu_title?.toLowerCase().includes(q) ||
                        sm.menu_name?.toLowerCase().includes(q)
                    )
            }))
            // 2) 검색어 있을 때 자식 없는 부모 제거
            .filter(m => !q || m.children.length > 0 || m.menu_name?.toLowerCase().includes(q));
    });

    onMounted(async () => {
        const { data } = await aibeesApi.get('/api/v1/master/menus', {
            params: { display_flag: 'Y', enabled_flag: 'Y' }
        });
        menuList.value = data.data;
    });

    const goTo = (path) => router.push({ path });

    const handleLogout = () => {
        userStore.logoutUser();
        router.push({ path: '/login' });
    };
</script>

<style lang="scss" scoped>
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

.common-menu {
    display: flex;
    flex-direction: column;
    height: 100%;
    background: $white;
    font-family: 'Pretendard', -apple-system, sans-serif;
    color: $gray-900;
    border-right: 1px solid $gray-200;
}

/* ── 헤더 버튼 ── */
.menu-header-btns {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px 16px 12px;
    border-bottom: 1px solid $gray-100;

    .icon-btn {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 6px 12px;
        border: 1px solid $gray-200;
        border-radius: 0.4rem;
        background: $white;
        color: $gray-700;
        font-size: 0.82rem;
        font-weight: 600;
        cursor: pointer;
        transition: border-color .15s, background .15s;

        &:hover {
            border-color: $blue;
            color: $blue;
            background: $gray-50;
        }

        &.logout-btn:hover {
            border-color: $red;
            color: $red;
        }
    }
}

/* ── 유저 카드 ── */
.menu-user {
    margin: 16px;
    padding: 14px 16px;
    background: $gray-50;
    border: 1px solid $gray-200;
    border-radius: 0.6rem;
    display: flex;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;

    .user-avatar {
        width: 38px;
        height: 38px;
        border-radius: 50%;
        background: $navy;
        color: $white;
        font-size: 1rem;
        font-weight: 700;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
    }

    .user-info {
        flex: 1;
        min-width: 0;

        .user-name {
            margin: 0 0 2px;
            font-size: 0.92rem;
            font-weight: 700;
            color: $gray-900;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .user-id {
            margin: 0;
            font-size: 0.75rem;
            color: $gray-500;
        }
    }

    .role-badges {
        display: flex;
        flex-wrap: wrap;
        gap: 4px;

        .role-badge {
            font-size: 0.68rem;
            font-weight: 700;
            padding: 2px 8px;
            border-radius: 0.3rem;
            background: #dbe4ff;
            color: $navy;
            border: 1px solid #bac8ff;
            text-transform: uppercase;
        }
    }
}

/* ── 검색 ── */
.menu-search-input {
    position: relative;
    margin: 0 16px 12px;

    .search-icon {
        position: absolute;
        left: 10px;
        top: 50%;
        transform: translateY(-50%);
        color: $gray-400;
        pointer-events: none;
    }

    .search-input {
        width: 100%;
        box-sizing: border-box;
        padding: 8px 12px 8px 32px;
        border: 1px solid $gray-200;
        border-radius: 0.4rem;
        background: $gray-50;
        font-size: 0.83rem;
        color: $gray-900;
        outline: none;
        font-family: inherit;
        transition: border-color .15s;

        &::placeholder { color: $gray-400; }
        &:focus { border-color: $blue; background: $white; }
    }
}

/* ── 메뉴 목록 ── */
.menu-list {
    flex: 1;
    overflow-y: auto;
    padding: 0 8px 24px;

    .main-ul {
        list-style: none;
        padding: 0;
        margin: 0;
    }

    .main-li {
        margin-bottom: 4px;
    }

    .main-name {
        padding: 6px 10px;
        font-size: 0.7rem;
        font-weight: 700;
        color: $gray-400;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        border-bottom: 1px solid $gray-100;
        margin: 8px 2px 2px;
    }

    .sub-ul {
        list-style: none;
        padding: 0;
        margin: 0;
    }

    .sub-li {
        border-radius: 0.4rem;
        overflow: hidden;
    }

    .menu-link {
        display: flex;
        flex-direction: column;
        padding: 9px 12px;
        cursor: pointer;
        border-radius: 0.4rem;
        transition: background .12s;

        &:hover {
            background: $gray-50;
        }

        &:active {
            background: #dbe4ff;
        }

        .link-title {
            font-size: 0.88rem;
            font-weight: 600;
            color: $gray-900;
        }

        .link-sub {
            font-size: 0.75rem;
            color: $gray-400;
            margin-top: 1px;
        }
    }
}
</style>