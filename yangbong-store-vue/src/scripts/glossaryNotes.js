/**
 * 용어 사전 "내 표시" — 즐겨찾기 · 헷갈려요 · 알아요.
 * 이 기기(브라우저/앱) 안에만 저장한다. 서버에는 보내지 않으므로 기기를 바꾸면 따라오지 않는다.
 *
 * 저장 모양: { fav: [id], confused: [id], known: [id] }
 * 키는 용어의 id(영문)라서, 표제어를 고쳐도 표시가 유지된다.
 * "헷갈려요"와 "알아요"는 서로 반대 뜻이라 하나를 켜면 다른 하나는 꺼진다.
 */
import { ref } from 'vue';

const STORAGE_KEY = 'glossaryNotes.v1';

const empty = () => ({ fav: [], confused: [], known: [] });

const load = () => {
    try {
        const v = JSON.parse(localStorage.getItem(STORAGE_KEY));
        if (!v || typeof v !== 'object') return empty();
        return {
            fav: Array.isArray(v.fav) ? v.fav : [],
            confused: Array.isArray(v.confused) ? v.confused : [],
            known: Array.isArray(v.known) ? v.known : [],
        };
    } catch {
        return empty();
    }
};

const state = ref(load());

const save = () => {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(state.value)); } catch { /* 저장 못 해도 이번 화면에서는 동작 */ }
};

const flip = (list, id, on) => {
    const has = list.includes(id);
    if (on && !has) return [...list, id];
    if (!on && has) return list.filter(x => x !== id);
    return list;
};

export function useGlossaryNotes() {
    const isFav = (id) => state.value.fav.includes(id);
    const isConfused = (id) => state.value.confused.includes(id);
    const isKnown = (id) => state.value.known.includes(id);

    const toggleFav = (id) => {
        state.value.fav = flip(state.value.fav, id, !isFav(id));
        save();
    };
    const toggleConfused = (id) => {
        const on = !isConfused(id);
        state.value.confused = flip(state.value.confused, id, on);
        if (on) state.value.known = flip(state.value.known, id, false);
        save();
    };
    const toggleKnown = (id) => {
        const on = !isKnown(id);
        state.value.known = flip(state.value.known, id, on);
        if (on) state.value.confused = flip(state.value.confused, id, false);
        save();
    };

    return { state, isFav, isConfused, isKnown, toggleFav, toggleConfused, toggleKnown };
}
