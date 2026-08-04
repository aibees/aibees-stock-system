// useThemeList.js
import aibeesApi from './aibeesApi.js'

export async function getThemeList(dateStr, themeName = '') {
    try {
        const { data } = await aibeesApi.get('/api/v1/themes', {
            params: {
                ymd: dateStr.replaceAll('-', ''),
                themeName
            }
        });

        return data.data.map(t => ({
            ...t,
            per_today: Number(t.per_today).toFixed(2),
            three_day_avg: Number(t.three_day_avg).toFixed(2)
        }));
    } catch (err) {
        console.error('[getThemeList 에러]', err);
        return [];
    }
}