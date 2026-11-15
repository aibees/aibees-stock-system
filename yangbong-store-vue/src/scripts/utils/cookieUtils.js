/**
 * cookie 유틸리티
 * localStorage 대신 쿠키를 사용해 브라우저 재시작 후에도 세션을 유지한다.
 */

/**
 * @param {string} name  쿠키 이름
 * @param {string} value 쿠키 값
 * @param {number} days  만료일 (기본 30일)
 */
export const setCookie = (name, value, days = 30) => {
    const expires = new Date(Date.now() + days * 864e5).toUTCString();
    document.cookie = `${name}=${encodeURIComponent(value)}; expires=${expires}; path=/; SameSite=Lax`;
};

/**
 * @param {string} name 쿠키 이름
 * @returns {string|null}
 */
export const getCookie = (name) => {
    const match = document.cookie
        .split('; ')
        .find(row => row.startsWith(name + '='));
    return match ? decodeURIComponent(match.split('=')[1]) : null;
};

/**
 * @param {string} name 쿠키 이름
 */
export const removeCookie = (name) => {
    document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/; SameSite=Lax`;
};
