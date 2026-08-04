<template>
    <div class="header">
        <div class="left">
            <div class="title">{{ title }}</div>
        </div>
        <div class="right">
            <div class="group" @click="goTo('group')">
                <div>즐겨찾기</div>
            </div>
            <div class="users" v-if="isUser" ref="userMenuRef">
                <div
                    class="user-btn"
                    @click.stop="toggleUserMenu"
                    :aria-expanded="userMenuOpen ? 'true' : 'false'"
                    aria-haspopup="menu" >
                    {{ userName }} 님
                    <span class="caret" :class="{ open: userMenuOpen }"></span>
                </div>

                <transition name="fade">
                    <ul
                        v-show="userMenuOpen"
                        class="user-dropdown profile-menu"
                        role="menu"
                        @click.stop >
                        <!-- 프로필 헤더 -->
                        <li class="profile" aria-hidden="true">
                            <div class="avatar" aria-hidden="true">
                                <!-- 심플 사용자 아이콘 -->
                                <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                                <circle
                                    cx="12"
                                    cy="8"
                                    r="4"
                                    stroke="currentColor"
                                    stroke-width="1.5"
                                />
                                <path
                                    d="M4 20c0-4 4-6 8-6s8 2 8 6"
                                    stroke="currentColor"
                                    stroke-width="1.5"
                                    stroke-linecap="round"
                                />
                                </svg>
                            </div>
                            <div class="meta">
                                <div class="name">{{ userName }}</div>
                            </div>
                        </li>

                        <li class="separator" aria-hidden="true"></li>

                        <!-- 개인설정 -->
                        <li class="menu-item" role="menuitem" @click="goUserOption">
                            <span class="icon" aria-hidden="true">⚙</span>
                            개인설정
                        </li>

                        <li class="separator" aria-hidden="true"></li>

                        <!-- 로그아웃 -->
                        <li class="logout" role="menuitem" @click="logout">
                            <span class="icon" aria-hidden="true">↻</span>
                            로그아웃
                        </li>
                    </ul>
                </transition>
            </div>

            <div class="users" @click="goTo('login')" v-else>
                <div>로그인</div>
            </div>
        </div>
    </div>
</template>


<script setup>
import { assUserSession } from "../../../scripts/stores/user-stores";
import { ref, toRefs, onMounted, onBeforeUnmount } from "vue";
import { useRouter } from "vue-router";

// 드롭다운 상태
const userMenuOpen = ref(false);
const userMenuRef = ref(null);

const toggleUserMenu = () => {
  userMenuOpen.value = !userMenuOpen.value;
};
const closeUserMenu = () => {
  userMenuOpen.value = false;
};

const onDocClick = (e) => {
  if (!userMenuRef.value) return;
  if (!userMenuRef.value.contains(e.target)) closeUserMenu();
};
const onKeyDown = (e) => {
  if (e.key === "Escape") closeUserMenu();
};

const userSession = assUserSession();
const props = defineProps({ prop_title: String });
const title = ref("");
const isUser = ref(false);
const userName = ref("");
const router = useRouter();

const loginCheckRoutes = ["group"];

onMounted(() => {
  title.value = toRefs(props).prop_title.value;
  isUser.value = userSession.isUserSession();
  userName.value = userSession.getUserInfo;

  // 드롭다운 외부클릭/ESC 닫기
  document.addEventListener("click", onDocClick, true);
  document.addEventListener("keydown", onKeyDown);
});

onBeforeUnmount(() => {
  document.removeEventListener("click", onDocClick, true);
  document.removeEventListener("keydown", onKeyDown);
});

// 개인설정 이동
const goUserOption = () => {
  closeUserMenu();
  router.push("/user-option");
};

// 로그아웃
const logout = () => {
    userSession.logoutUser(); // pinia 상태 + sessionStorage + localStorage 모두 초기화
    closeUserMenu();
    router.push('/home');
};

// 로그인 여부 비활성화
const goTo = (name) => {
    if (loginCheckRoutes.includes(name) && !userSession.isUserSession()) {
        alert("로그인이 필요한 페이지입니다. 로그인메뉴로 이동합니다.");
        router.push({ name: 'login' });
        return;
    }

    router.push({ name });
};
</script>
<style src="@@/comm/Headers.scss" scoped />