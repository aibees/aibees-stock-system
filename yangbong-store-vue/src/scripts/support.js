/** 고객지원: 경로, 문의 이메일, 메일 쓰기 링크. */
import { Capacitor } from '@capacitor/core';
import pkg from '../../package.json';

export const SUPPORT_PATH = '/support';
export const FAQ_PATH = '/support/faq';
export const CONTACT_PATH = '/support/contact';
export const TERMS_PATH = '/support/terms';
export const PRIVACY_PATH = '/support/privacy';
export const LICENSES_PATH = '/support/licenses';

export const SUPPORT_EMAIL = 'chagoklabs@gmail.com';

const deviceText = () => {
    const ua = navigator.userAgent;
    const os = /iPhone|iPad|iPod/.test(ua) ? 'iOS' : (/Android/.test(ua) ? 'Android' : '웹');
    return `${os} · ${Capacitor.isNativePlatform() ? '앱' : '브라우저'}`;
};

/** 앱 버전과 기기 정보를 미리 채운 메일 쓰기 링크. 개인 식별 정보는 넣지 않는다. */
export const contactMailto = () => {
    const subject = '[양봉상회 문의] ';
    const body = ['문의 내용:', '', '', '', '---', `앱 버전: ${pkg.version}`, `기기: ${deviceText()}`].join('\n');
    return `mailto:${SUPPORT_EMAIL}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
};
