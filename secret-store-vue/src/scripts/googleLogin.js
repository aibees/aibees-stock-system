/**
 * 구글 로그인(웹 전용) — Google Identity Services(GIS) 버튼.
 *
 * 흐름: GIS 가 팝업으로 구글 계정을 고르게 한 뒤 ID 토큰(credential)을 콜백으로 준다 → POST /api/oauth/google.
 * 서버가 ID 토큰을 구글 공개키로 직접 검증하고 네이버와 같은 규칙으로 로그인·연결·가입한다.
 * nonce 는 이번 초기화에서 만든 값과 토큰 속 값이 같은지 서버가 확인한다(다른 곳에서 받은 토큰 재사용 방지).
 *
 * iOS 앱(WKWebView)에서는 구글이 OAuth 화면을 막으므로(disallowed_useragent) 버튼을 띄우지 않는다.
 * 클라이언트 ID 는 master_infos GOOGLE_AUTH 의 GOOGLE_WEB_ID — 없으면 버튼을 띄우지 않는다.
 */
import { Capacitor } from '@capacitor/core';
import aibeesApi from './aibeesApi.js';

const GIS_SRC = 'https://accounts.google.com/gsi/client';
let gisLoading = null;

export const googleLoginAvailable = () => !Capacitor.isNativePlatform();

const loadGis = () => {
    if (window.google?.accounts?.id) return Promise.resolve();
    if (!gisLoading) {
        gisLoading = new Promise((resolve, reject) => {
            const s = document.createElement('script');
            s.src = GIS_SRC;
            s.async = true;
            s.onload = () => resolve();
            s.onerror = () => { gisLoading = null; reject(new Error('GIS 스크립트를 불러오지 못함')); };
            document.head.appendChild(s);
        });
    }
    return gisLoading;
};

const fetchWebClientId = async () => {
    const { data } = await aibeesApi.get('/api/oauth/infos/google');
    return (data?.data ?? []).find((d) => d.key_type === 'GOOGLE_WEB_ID')?.key_value ?? '';
};

const randomHex = () =>
    Array.from(crypto.getRandomValues(new Uint8Array(16)), (b) => b.toString(16).padStart(2, '0')).join('');

/**
 * el 에 구글 버튼을 그린다. 버튼을 그렸으면 true(설정 없음·앱·스크립트 실패면 false).
 * onResponse(data) — POST /api/oauth/google 응답의 data(로그인 결과 또는 consentRequired)
 * onError(message)
 */
export const renderGoogleButton = async (el, { onStart, onResponse, onError }) => {
    if (!el || !googleLoginAvailable()) return false;
    let clientId;
    try {
        clientId = await fetchWebClientId();
        if (!clientId) return false;
        await loadGis();
    } catch (err) {
        console.error(err);
        return false;
    }

    const nonce = randomHex();
    window.google.accounts.id.initialize({
        client_id: clientId,
        nonce,
        ux_mode: 'popup',
        auto_select: false,
        itp_support: true,
        callback: async ({ credential }) => {
            onStart?.();
            try {
                const { data } = await aibeesApi.post('/api/oauth/google', { credential, nonce });
                if (!data?.success) return onError(data?.error?.message ?? '구글 로그인에 실패했어요.');
                onResponse(data.data);
            } catch (err) {
                onError(err?.response?.data?.error?.message ?? err?.error?.message ?? '구글 로그인에 실패했어요.');
            }
        },
    });
    window.google.accounts.id.renderButton(el, {
        type: 'standard',
        theme: 'outline',
        size: 'large',
        text: 'continue_with',
        shape: 'rectangular',
        logo_alignment: 'center',
        locale: 'ko',
        width: Math.min(400, contentWidth(el) || 360),   // GIS 최대 400px
    });
    return true;
};

// el 이 아직 숨겨져 있으면(v-show) 폭이 0 이라 부모의 내용 폭으로 맞춘다(다른 버튼과 같은 폭)
const contentWidth = (el) => {
    if (el.clientWidth) return el.clientWidth;
    const parent = el.parentElement;
    if (!parent) return 0;
    const cs = getComputedStyle(parent);
    return parent.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
};
