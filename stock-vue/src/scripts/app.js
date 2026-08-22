import { createApp } from 'vue'
import App from '@/components/App.vue'
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
        faPlus, faDownload, faPen, faTrash, 
        faUpload, faBars, faSave, faCircleXmark, 
        faCaretLeft, faCaretRight, faBurger } from "@fortawesome/free-solid-svg-icons";

library.add(faMagnifyingGlass, faXmark, faMinus, faHome,
        faPlus, faDownload, faPen, faTrash, faUpload, 
        faBars, faSave, faCircleXmark, faCaretLeft, 
        faCaretRight, faBurger);
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
        initPushNotifications();
    });
    // ====================================================================
})
// ===========================

export default app
