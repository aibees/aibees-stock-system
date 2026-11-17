import { createApp } from 'vue'
import App from '@/components/App.vue'
// 테마 토큰(--sc-*). 컴포넌트 스타일보다 먼저 들어가야 하므로 맨 위에서 읽는다.
import '@@/theme.css'
import { initTheme } from './theme.js'
// 저장된 테마를 마운트 전에 <html data-theme> 에 반영 — 첫 화면이 기본 테마로 번쩍이지 않게.
initTheme();
const app = createApp(App)

// ===== 레이어 팝업 드래그 디렉티브 =====
import draggable from './directives/draggable.js'
app.directive('draggable', draggable)
// =======================================

// ===== global axios =====
import axios from 'axios';

const axiosInstance = axios.create({
    
})
app.provide('$axios', axiosInstance)
// ========================

// ===== pinia store Add =====
import { createPinia } from 'pinia';
import piniaPersist from 'pinia-plugin-persistedstate';
const pinia = createPinia();
pinia.use(piniaPersist)
app.use(pinia);
// ===========================

// ===== FontAwesomeIcon Add =====
import { library } from "@fortawesome/fontawesome-svg-core";
import { FontAwesomeIcon } from "@fortawesome/vue-fontawesome";
import { faMagnifyingGlass, faXmark, faMinus, faHome,
        faPlus, faDownload, faPen, faTrash, faComputer,
        faUpload, faBars, faSave, faCircleXmark, 
        faCaretLeft, faCaretRight, faBurger } from "@fortawesome/free-solid-svg-icons";

library.add(faMagnifyingGlass, faXmark, faMinus, faHome,
        faPlus, faDownload, faPen, faTrash, faUpload, 
        faBars, faSave, faCircleXmark, faCaretLeft, 
        faCaretRight, faBurger, faComputer);
app.component("font-awesome-icons", FontAwesomeIcon)
// ===============================

// ===== Event Bus =====
import mitt from 'mitt';
const emitter = new mitt();
app.provide('emitter', emitter);
// =====================

// ===== Router Resigrer =====
import { setRouterToApp } from './router'
setRouterToApp().then(router => {
    app.use(router);
    app.mount('#app');

    // ===== 푸시 알림(FCM) 등록 — 네이티브(iOS/Android) 앱에서만 동작 =====
    import('./usePushNotifications').then(({ initPushNotifications }) => {
        return initPushNotifications();
    });
    // ====================================================================

    // AdMob 은 시작하지 않는다 — 비밀상회는 광고 없는 내부 앱(2026-11-17).
})
// ===========================

export default app
