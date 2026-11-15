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
    const pushReady = import('./usePushNotifications').then(({ initPushNotifications }) => {
        return initPushNotifications();
    });
    // ====================================================================

    // ===== AdMob 배너 — 네이티브 앱에서만 동작. 푸시 초기화 "다음에" 시작한다 =====
    //   첫 실행에는 푸시 권한 팝업과 iOS 추적(ATT) 팝업이 모두 뜨는데, 시스템 팝업이 이미 떠 있는
    //   상태에서 ATT 를 요청하면 조용히 무시될 수 있다. 푸시는 사용자가 권한에 응답할 때까지
    //   기다리므로 그 뒤에 광고를 시작하면 두 팝업이 순서대로 뜬다.
    //   푸시가 멈춰도 광고가 영원히 막히지 않게 20초 상한을 둔다. 푸시 실패는 광고와 무관하다.
    Promise.race([
        pushReady.catch(() => {}),
        new Promise((resolve) => setTimeout(resolve, 20000)),
    ]).then(() => import('./useAdMob')).then(({ initAdMob }) => initAdMob());
    // ====================================================================
})
// ===========================

export default app
