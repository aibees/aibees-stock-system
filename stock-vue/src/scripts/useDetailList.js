// useDetailList.js
import aibeesApi from './aibeesApi.js';

/**
 * 특정 테마 코드에 대한 상세 리스트를 받아옵니다.
 * @param {string} themeCode - 테마 코드
 * @param {string} ymd - 'YYYY-MM-DD' 형식의 날짜
 * @returns {Array} 디테일 리스트 (주식 목록)
 */
export async function getThemeDetailList(themeCode, ymd) {
    if (!themeCode || !ymd) return [];

    try {
        const { data } = await aibeesApi.get(`/api/v1/themes/${themeCode}`, {
            params: {
                ymd: ymd.replaceAll('-', '')
            }
        });

        return data.data.map(d => ({
            ...d,
            per_rate: Number(d.per_rate).toFixed(2),
            three_day_avg: Number(d.three_day_avg).toFixed(2)
        }));
    } catch (err) {
        console.error('[getThemeDetailList 에러]', err);
        return [];
    }
}
