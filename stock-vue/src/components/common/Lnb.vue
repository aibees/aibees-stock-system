<template>
    <!-- ── Web: 상단 글로벌 내비게이션 ── -->
    <nav id="comm-lnb-web">
        <div class="lnb-web-inner">
            <div class="lnb-brand" @click="goPath('/home')">
                <font-awesome-icons :icon="['fa-solid', 'fa-home']" />
                <span>Aibees Stock</span>
            </div>

            <ul class="lnb-menu">
                <li v-for="m in topMenus" :key="m.menu_code" class="lnb-item"
                    :class="{ active: isActiveTop(m), 'has-children': hasChildren(m) }"
                    @mouseenter="openCode = m.menu_code" @mouseleave="openCode = ''"
                    @click="onTopClick(m)">
                    <span class="lnb-item-label">
                        {{ m.menu_title || m.menu_name }}
                        <span v-if="hasChildren(m)" class="caret" :class="{ open: openCode === m.menu_code }"></span>
                    </span>

                    <transition name="drop">
                        <ul v-if="hasChildren(m) && openCode === m.menu_code" class="lnb-dropdown">
                            <li v-for="c in visibleChildren(m)" :key="c.menu_code"
                                :class="{ active: isActiveChild(m, c) }" @click.stop="goChild(m, c)">
                                {{ c.menu_title || c.menu_name }}
                            </li>
                        </ul>
                    </transition>
                </li>
            </ul>
        </div>
    </nav>

    <!-- ── Mobile: 하단 탭 바 ── -->
    <div id="comm-lnb">
        <div class="left">
            <div @click="goPath('/home')">
                <font-awesome-icons :icon="['fa-solid', 'fa-home']" />
            </div>
        </div>
        <div class="right">
            <div @click="goPath('/menu')">
                <font-awesome-icons :icon="['fa-solid', 'fa-bars']" />
            </div>
        </div>
    </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { assUserSession } from "../../scripts/stores/user-stores";

const router = useRouter();
const route = useRoute();
const userSession = assUserSession();

const isUser = ref(false);
const userName = ref('');
const allMenu = ref([]);
const openCode = ref('');

const isAdmin = computed(() => {
    const roles = userSession.getRole ?? [];
    return roles.some(r => r.toUpperCase() === 'ADMIN' || r === '시스템 관리자');
});

console.log("is Admin : " + isAdmin.value)


/* ── 노출 가능한 최상위 메뉴 (표시/사용/권한 필터 + 정렬) ── */
const topMenus = computed(() => {
    return (allMenu.value ?? [])
        .filter(m => m.display_flag !== 'N' && m.enabled_flag !== 'N')
        .filter(m => m.admin_only !== 'Y' || isAdmin.value)
        .sort((a, b) => (a.sort ?? 0) - (b.sort ?? 0));
});

const visibleChildren = (m) => {
    return (m.children ?? [])
        .filter(c => c.display_flag !== 'N' && c.enabled_flag !== 'N')
        .filter(c => c.admin_only !== 'Y' || isAdmin.value)
        .sort((a, b) => (a.sort ?? 0) - (b.sort ?? 0));
};

const hasChildren = (m) => visibleChildren(m).length > 0;

/* ── 활성 메뉴 판별 ── */
const currentTop = computed(() => route.path.split('/').filter(p => p !== '')[0] ?? '');

const isActiveTop = (m) => currentTop.value === m.menu_path;

const isActiveChild = (m, c) => route.path === `/${m.menu_path}/${c.menu_path}`;

/* ── 이동 ── */
const goPath = (path) => {
    router.push({ path });
};

const goChild = (m, c) => {
    openCode.value = '';
    router.push({ path: `${m.menu_path}/${c.menu_path}` });
};

const onTopClick = (m) => {
    const children = visibleChildren(m);
    if (children.length > 0) {
        // 자식이 있으면 첫번째 자식으로 이동 (드롭다운은 hover로 노출)
        goChild(m, children[0]);
    } else {
        goPath(`${m.menu_path}`);
    }
};

onMounted(() => {
    isUser.value = userSession.isUserSession();
    userName.value = userSession.getUserInfo;
    allMenu.value = userSession.loadMenuList() ?? [];
    console.log(allMenu.value);
console.log(userSession.getRole);
});
</script>

<style lang="scss" scoped>
@use '@@/__variables.scss' as *;

/* ──────────────────────────────────────────────
   Web 상단 내비게이션
   - 모바일(640px 미만)에서는 숨김
────────────────────────────────────────────── */
#comm-lnb-web {
    display: none;
    position: sticky;
    top: 0;
    z-index: 900;
    background: #1c3d6e;
    box-shadow: 0 2px 8px rgba(0, 0, 0, .08);

    @include mobile {
        display: block;
    }
}

.lnb-web-inner {
    max-width: 1400px;
    margin: 0 auto;
    height: 46px;
    display: flex;
    align-items: center;
    padding: 0 20px;
    gap: 28px;
}

.lnb-brand {
    display: flex;
    align-items: center;
    gap: 8px;
    color: #fff;
    font-weight: 700;
    font-size: 0.92rem;
    white-space: nowrap;
    cursor: pointer;
    opacity: .95;
    transition: opacity .15s;

    &:hover {
        opacity: 1;
    }
}

.lnb-menu {
    display: flex;
    align-items: center;
    height: 100%;
    list-style: none;
    margin: 0;
    padding: 0;
    flex: 1;
    gap: 4px;
}

.lnb-item {
    position: relative;
    height: 100%;
    display: flex;
    align-items: center;
    cursor: pointer;

    .lnb-item-label {
        display: flex;
        align-items: center;
        gap: 6px;
        height: 100%;
        padding: 0 14px;
        color: rgba(255, 255, 255, .82);
        font-size: 0.86rem;
        font-weight: 600;
        white-space: nowrap;
        border-bottom: 2px solid transparent;
        transition: color .15s, border-color .15s;
    }

    &:hover .lnb-item-label,
    &.active .lnb-item-label {
        color: #fff;
        border-bottom-color: #4dabf7;
    }

    .caret {
        width: 0;
        height: 0;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-top: 5px solid currentColor;
        opacity: .8;
        transition: transform .15s ease;

        &.open {
            transform: rotate(180deg);
        }
    }
}

/* 드롭다운 */
.lnb-dropdown {
    position: absolute;
    top: 100%;
    left: 0;
    min-width: 180px;
    background: #fff;
    border: 1px solid #e9ecef;
    border-radius: 0 0 0.5rem 0.5rem;
    box-shadow: 0 10px 24px rgba(0, 0, 0, .12);
    list-style: none;
    margin: 0;
    padding: 6px;
    z-index: 950;

    li {
        padding: 9px 12px;
        font-size: 0.82rem;
        font-weight: 500;
        color: #333333;
        border-radius: 0.35rem;
        cursor: pointer;
        white-space: nowrap;
        transition: background .12s, color .12s;

        &:hover {
            background: #f1f5fb;
            color: #1971c2;
        }

        &.active {
            background: #e7f0fd;
            color: #1c3d6e;
            font-weight: 700;
        }
    }
}

.drop-enter-active,
.drop-leave-active {
    transition: opacity .12s ease, transform .12s ease;
}

.drop-enter-from,
.drop-leave-to {
    opacity: 0;
    transform: translateY(-4px);
}

.lnb-right {
    display: flex;
    align-items: center;
    white-space: nowrap;

    .lnb-user {
        color: rgba(255, 255, 255, .85);
        font-size: 0.8rem;
        font-weight: 600;
    }
}

/* ──────────────────────────────────────────────
   Mobile 하단 탭 바
   - 데스크탑(640px 이상)에서는 숨김
────────────────────────────────────────────── */
#comm-lnb {
    position: fixed;
    bottom: 0;
    left: 0;
    width: 100%;
    height: 2.5rem;
    background-color: #171717;
    padding: calc(8px + env(safe-area-inset-bottom)) 0;
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-top-left-radius: 10px;
    border-top-right-radius: 10px;
    z-index: 1000;
    font-size: 1.4rem;
    color: #fff;

    @include mobile {
        display: none;
    }

    .left {
        padding: 0.4rem 1.8rem;
    }

    .right {
        width: 1.8rem;
        padding: 0.4rem 1.8rem;
        display: flex;
        justify-content: end;
        align-items: center;
    }
}
</style>
