<template>
    <div class="common-menu">

        <!-- ── 상단바: 사용자 + 홈/로그아웃 ──
             사용자 이름을 별도 카드로 크게 띄우던 것을 여기로 합쳤다. 메뉴 화면의
             주인공은 메뉴 목록이지 사용자 정보가 아니다 — 아바타+이름을 한 줄로
             줄여 목록이 더 위에서 시작하게 한다. -->
        <div class="menu-header-btns">
            <div class="header-user">
                <span class="user-avatar">{{ userInitial }}</span>
                <span class="user-name">{{ userName }}</span>
            </div>
            <div class="header-actions">
                <button class="icon-btn" @click="goTo('/home')" title="홈으로">
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"
                        fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
                        <polyline points="9 22 9 12 15 12 15 22"/>
                    </svg>
                </button>
                <button class="icon-btn logout-btn" @click="handleLogout" title="로그아웃">
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"
                        fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
                        <polyline points="16 17 21 12 16 7"/>
                        <line x1="21" y1="12" x2="9" y2="12"/>
                    </svg>
                </button>
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
                <!-- 상위/하위 모두 menu_title(한글)을 쓴다. menu_name 은 영문 슬러그라
                     병기하면 목록이 두 배로 길어지고 스캔이 느려진다. 문구를 바꾸고
                     싶으면 코드가 아니라 master_menu.menu_title 을 고치면 된다. -->
                <li v-for="m in filteredMenuList" :key="m.menu_code" class="main-li">
                    <div class="main-name">{{ m.menu_title || m.menu_name }}</div>
                    <ul class="sub-ul">
                        <li v-for="sm in m.children" :key="sm.menu_code" class="sub-li">
                            <div class="menu-link" @click="goTo(m.menu_path + '/' + sm.menu_path)">
                                <span class="link-title">{{ sm.menu_title || sm.menu_name }}</span>
                            </div>
                        </li>
                    </ul>
                </li>
            </ul>
        </div>

    </div>
</template>

<script setup>
    import { ensureAccess } from '@scripts/useAccess.js';
    import { assUserSession } from '@scripts/stores/user-stores.js';

    const router    = useRouter();
    const userStore = assUserSession();

    /* ── 유저 정보 ── */
    const userName  = computed(() => userStore.getUserInfo || 'Anonymous');
    const userId    = computed(() => userStore.user.loginInfo.user_id || '');
    const userInitial = computed(() => (userName.value?.[0] ?? '?').toUpperCase());

    /* ── 메뉴 ──
     * 권한(role_menu)이 반영된 트리를 쓴다. 서버(/master/menus/my)가 접근 가능한 메뉴만
     * 내려주므로 여기서 admin_only/isAdmin 으로 다시 거르지 않는다. */
    const searchQuery = ref('');

    const menuList = computed(() =>
        (userStore.user.menuList ?? [])
            .filter(m => m.display_flag === 'Y')
            .map(m => ({ ...m, children: (m.children ?? []).filter(sm => sm.display_flag === 'Y') }))
    );

    const filteredMenuList = computed(() => {
        const q = searchQuery.value.trim().toLowerCase();

        return menuList.value
            .map(m => ({
                ...m,
                children: m.children.filter(sm => !q ||
                    sm.menu_title?.toLowerCase().includes(q) ||
                    sm.menu_name?.toLowerCase().includes(q)
                )
            }))
            // 검색어 있을 때 자식 없는 부모 제거
            .filter(m => !q || m.children.length > 0 || m.menu_name?.toLowerCase().includes(q));
    });

    onMounted(() => ensureAccess());

    const goTo = (path) => router.push({ path });

    const handleLogout = () => {
        userStore.logoutUser();
        router.push({ path: '/login' });
    };
</script>

<style lang="scss" scoped>
$white:    #ffffff;
$gray-50:  #fafafa;
$gray-100: #efefef;
$gray-200: #dcdcdc;
$gray-300: #c4c4c4;
$gray-400: #9a9a9a;
$gray-500: #737373;
$gray-700: #3d3d3d;
$gray-900: #141414;
$blue:     #141414;
$navy:     #141414;
$red:      #141414;

.common-menu {
    display: flex;
    flex-direction: column;
    /* height:100% 는 조상 체인에 확정 높이가 있어야 먹는다. #app~body 가 그렇지
     * 않아 높이가 붕괴되고, 그러면 .menu-list 의 flex:1 + overflow-y:auto 가
     * 동작하지 않아 목록 끝(추천성과 등)이 고정 탭바 뒤로 숨는다.
     * dvh 로 뷰포트 높이를 직접 잡고, 미지원 브라우저용으로 vh 를 앞에 둔다. */
    min-height: 100vh;
    min-height: 100dvh;
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
    gap: 12px;
    padding: 12px 16px;
    border-bottom: 1px solid $gray-100;

    /* 사용자 표시를 상단바에 녹인다 — 아바타 24px + 이름 한 줄. */
    .header-user {
        display: flex;
        align-items: center;
        gap: 8px;
        min-width: 0;          // 긴 이름이 버튼을 밀어내지 않게

        .user-avatar {
            width: 24px;
            height: 24px;
            background: $navy;
            color: $white;
            font-size: 0.72rem;
            font-weight: 700;
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
        }

        .user-name {
            font-size: 0.85rem;
            font-weight: 600;
            color: $gray-900;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
    }

    .header-actions {
        display: flex;
        gap: 6px;
        flex-shrink: 0;
    }

    .icon-btn {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 6px 10px;
        border: 1px solid $gray-200;
        border-radius: 0;
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

/* 유저 카드(.menu-user)는 상단바(.header-user)로 합치면서 제거했다. */

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
        border-radius: 0;
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

    /* 상위 항목(주식정보/차트메뉴/트레이드…)은 하위보다 크고 진해야 묶음이 보인다.
     * 이전엔 0.7rem·회색·uppercase 라 하위(0.88rem·진한색)보다 작고 흐려서
     * 위계가 뒤집혀 있었다. uppercase 도 뺀다 — 한글에는 효과가 없고 영문
     * 폴백에서만 모양을 바꿔 들쭉날쭉해진다. */
    .main-name {
        padding: 6px 10px;
        font-size: 1rem;
        font-weight: 700;
        color: $gray-900;
        letter-spacing: -0.01em;
        text-align: left;
        border-bottom: 1px solid $gray-200;
        margin: 14px 2px 4px;
    }

    .sub-ul {
        list-style: none;
        padding: 0;
        margin: 0;
    }

    .sub-li {
        border-radius: 0;
        overflow: hidden;
    }

    /* 왼쪽 정렬. App.vue 의 #app { text-align: center } 가 전역으로 상속되어
     * 메뉴 텍스트까지 가운데 정렬돼 있었다 — 목록은 왼쪽 정렬이라야 눈이
     * 한 줄로 훑어진다. */
    .menu-link {
        display: flex;
        flex-direction: column;
        align-items: flex-start;
        text-align: left;
        padding: 10px 12px;
        cursor: pointer;
        border-radius: 0;
        transition: background .12s;

        &:hover {
            background: $gray-50;
        }

        &:active {
            background: #efefef;
        }

        /* 하위 항목은 상위(1rem/700)보다 작고 덜 진하게 — 위계가 보이도록. */
        .link-title {
            font-size: 0.88rem;
            font-weight: 500;
            color: $gray-700;
        }
    }
}
</style>