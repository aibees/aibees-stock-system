/**
 * FCM 푸시 알림 등록/수신 처리.
 *
 * @capacitor-firebase/messaging 사용 (기존 @capacitor/push-notifications 에서 교체).
 * 교체 이유: @capacitor/push-notifications 는 iOS에서 Firebase SDK를 거치지 않고
 * APNs raw device token(hex 문자열)을 그대로 'registration' 이벤트로 넘겨준다.
 * 서버(firebase-admin)는 FCM 등록 토큰을 기대하는데 raw APNs token을 그대로 보내면
 * "The registration token is not a valid FCM registration token" (INVALID_ARGUMENT)
 * 로 거부된다. @capacitor-firebase/messaging 은 네이티브 FirebaseMessaging SDK를 통해
 * APNs token → FCM token 교환을 내부적으로 처리해서 진짜 FCM 토큰을 돌려준다.
 * (Android는 원래부터 FCM SDK를 직접 쓰므로 이 문제가 없었다.)
 *
 * - 웹(브라우저)에서는 아무 것도 하지 않는다 — Capacitor.isNativePlatform() 로 분기.
 * - 흐름: 권한 요청 → (플러그인이 내부적으로 APNs 등록 + FCM 토큰 교환) →
 *   'tokenReceived' 이벤트로 FCM 토큰 수신 → 백엔드(app/api/v1/notify/register,
 *   py-stock-batch)에 업로드. 이벤트가 늦게 올 경우를 대비해 getToken() 도 한 번
 *   직접 호출해서 즉시 시도해본다(실패해도 무시 — 이벤트로 나중에 들어옴).
 * - "앱이 꺼져있어도 알림이 가야 한다"는 FCM 의 기본 동작(OS 시스템 알림)으로
 *   충족된다 — 이 파일이 직접 처리하는 건 "앱이 켜져있을 때(포그라운드) 뜨는
 *   toast" 뿐이다. 포그라운드에서는 OS 배너가 기본적으로 안 뜨기 때문에
 *   mariaToast 로 대신 보여준다.
 */
import { Capacitor } from '@capacitor/core';
import { FirebaseMessaging } from '@capacitor-firebase/messaging';
import { batchApi } from './aibeesApi';
import mariaToast from './mariaToast';
import { assUserSession } from './stores/user-stores';

let initialized = false;
// 플러그인이 마지막으로 넘겨준 FCM 토큰. 로그인/로그아웃 때 이 토큰으로 소유자만
// 바꿔 재등록하려면(syncPushRegistration) 들고 있어야 한다.
let currentToken = null;
// 마지막으로 서버에 올린 "토큰|user_id". 토큰만 비교하면 안 되는 이유는
// registerTokenToServer 주석 참고.
let lastSentKey = null;

export async function initPushNotifications() {
    console.log("[initPushNotifications] INIT : " + initialized);
    if (initialized) {
        return;
    }
    console.log("[initPushNotifications] isNativePlatform" + Capacitor.isNativePlatform())
    if (!Capacitor.isNativePlatform()) {
        return;
    } // 웹 배포는 skip

    initialized = true;

    try {
        let perm = await FirebaseMessaging.checkPermissions();
        console.log("[initPushNotifications] PERM : ");
        console.log(perm);
        if (perm.receive === 'prompt') {
            perm = await FirebaseMessaging.requestPermissions();
        }
        if (perm.receive !== 'granted') {
            console.warn('[push] 알림 권한이 거부되었습니다.');
            return;
        }

        // FCM 토큰이 (재)생성될 때마다 호출됨 — 최초 발급뿐 아니라 토큰 갱신 시에도 온다.
        FirebaseMessaging.addListener('tokenReceived', (event) => {
            console.log('[push] tokenReceived 이벤트 수신, token 길이=' + (event?.token?.length ?? 0)
                + ', token 앞 12자=' + (event?.token?.slice(0, 12) ?? ''));
            registerTokenToServer(event.token);
        });

        // APNs raw token 수신 로그(디버깅용) — 이게 뜨는데 tokenReceived 가 안 뜨면
        // Firebase 프로젝트에 APNs 인증키(Firebase Console > Cloud Messaging)가
        // 등록 안 되어 있을 가능성이 큼.
        FirebaseMessaging.addListener('apnsTokenReceived', (event) => {
            console.log('[push] apnsTokenReceived(raw APNs token) 앞 12자=' + (event?.token?.slice(0, 12) ?? ''));
        });

        console.log('[push] getToken() 직접 호출 시도');
        try {
            const { token } = await FirebaseMessaging.getToken();
            console.log('[push] getToken() 성공, token 앞 12자=' + (token?.slice(0, 12) ?? ''));
            registerTokenToServer(token);
        } catch (e) {
            // 아직 APNs 등록이 안 끝난 시점일 수 있음 — tokenReceived 이벤트로 나중에 들어옴.
            console.warn('[push] getToken() 즉시 호출 실패(무시, tokenReceived 대기):', e?.message);
        }

        // 포그라운드 수신 → toast. (백그라운드/종료 상태 수신은 OS 가 시스템
        // 알림으로 대신 띄운다 — 여기서 처리할 필요 없음)
        FirebaseMessaging.addListener('notificationReceived', (event) => {
            const noti = event.notification || {};
            const title = noti.title || noti.data?.title || '알림';
            const body = noti.body || noti.data?.body || '';
            mariaToast.info(body ? `${title} - ${body}` : title);
        });

        // 알림을 탭해서 앱을 열었을 때. 지금은 별도 화면 이동 없이 로그만 —
        // 필요해지면 event.notification.data.batch_code 등으로 라우팅 추가.
        FirebaseMessaging.addListener('notificationActionPerformed', (event) => {
            console.log('[push] 알림 탭:', event.notification);
        });
    } catch (e) {
        console.error('[push] 초기화 실패', e);
    }
}

/**
 * 이 기기의 push 소유자(user_id)를 서버에 다시 올린다 — 로그인/로그아웃 직후
 * user-stores 의 loginUser/logoutUser 에서 호출한다.
 *
 * 왜 필요한가: 등록(initPushNotifications)은 앱 mount 때 딱 한 번만 돌고,
 * FCM 토큰은 앱을 재설치하지 않으면 계속 같은 값이다. 그래서 "로그아웃 상태로
 * 앱을 켠 뒤 그 세션에서 로그인" 하면 토큰 행의 user_id 가 null 로 굳은 채
 * 남았다. 지금은 발송되는 push 가 전부 user 스코프라(배치 시작/종료=운영자
 * 1명, 체결/경보=worker 소유자) user_id 가 비어 있으면 알림이 아예 안 간다.
 *
 * 토큰이 아직 없으면(권한 거부/비네이티브/토큰 수신 전) 아무 것도 하지 않는다 —
 * 이후 tokenReceived 가 오면 그때의 로그인 상태로 등록된다.
 */
export function syncPushRegistration() {
    if (!Capacitor.isNativePlatform() || !currentToken) {
        return;
    }
    registerTokenToServer(currentToken);
}

async function registerTokenToServer(deviceToken) {
    if (!deviceToken) {
        return;
    }
    currentToken = deviceToken;

    // 호출부(이벤트 리스너 / syncPushRegistration)는 await 하지 않으므로 이 함수는
    // 절대 reject 되면 안 된다 — 세션 조회까지 전부 try 안에 둔다.
    try {
        const userSession = assUserSession();
        const platform = Capacitor.getPlatform(); // 'ios' | 'android'
        const userId = userSession.isUserSession()
            ? (userSession.user.loginInfo.user_id || null)
            : null;
        const roles = userSession.getRole ?? [];

        // 중복 전송 방지 키에 user_id 를 포함한다. 토큰만 비교하면(기존 동작) 같은
        // 기기에서 로그인/로그아웃으로 소유자가 바뀌어도 재등록이 막혀서 서버의
        // user_id 가 과거 값으로 굳는다 — syncPushRegistration 주석 참고.
        const sendKey = deviceToken + '|' + (userId ?? '');
        if (sendKey === lastSentKey) {
            return; // 같은 토큰+같은 소유자 = 이미 올림(tokenReceived + getToken() 둘 다 올 수 있음)
        }
        lastSentKey = sendKey;

        console.log('[push] 서버 등록 요청 → /api/v1/notify/register platform=' + platform
            + ' user_id=' + userId + ' baseURL=' + (batchApi.defaults?.baseURL ?? '(none)'));

        const resp = await batchApi.post('/api/v1/notify/register', {
            device_token: deviceToken,
            platform,
            user_id: userId,
            roles,
        });

        console.log('[push] 서버 등록 성공', JSON.stringify(resp.data));
    } catch (e) {
        // 실패했으면 "올렸다" 표시를 되돌린다 — 안 그러면 네트워크가 돌아와도
        // 같은 키라서 영구히 재시도되지 않는다(다음 tokenReceived / 로그인 때 재시도).
        lastSentKey = null;
        // [디버깅] 여기 안 뜨고 tokenReceived 로그만 있으면 → nginx 라우팅/CORS/네트워크 문제.
        console.error('[push] 서버 등록 실패', e?.response?.status, e?.message, JSON.stringify(e?.response?.data ?? ''));
    }
}
