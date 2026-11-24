/**
 * 트레이닝 진행 기록: 마친 단계의 key 목록.
 *
 * 가입 없이도 쓰므로 먼저 이 기기(localStorage 'yb-training')에 두고, 로그인하면 계정
 * (yangbong.user_training_progress, sql/yangbong/011 · API /api/v1/training/progress)과 맞춘다(2026-11-22).
 * 내 설정의 기본 보조지표는 그 지표의 단계를 마쳐야 열리므로, 기기만으로는 재설치·다른 기기에서 기록이 사라진다.
 *
 *   done      : 마친 단계 key 목록
 *   updatedAt : 마지막으로 바뀐 시각(ms)
 *   owner     : 이 기기 기록을 마지막으로 계정과 맞춘 user_id. null 이면 로그인 전에 쌓은 기록 →
 *               다음에 로그인하는 계정에 합친다. 다른 계정 것이면 합치지 않고 그 계정의 기록으로 바꾼다(기기를 같이 쓰는 경우).
 *
 * 계정 동기화(syncWithAccount)는 라우터 가드가 로그인 상태의 첫 이동 때 부른다.
 *   기록은 지우지 않고 쌓기만 하므로 맞출 때는 합집합 — 계정에만 있는 건 받아 오고, 기기에만 있는 건 올린다.
 *   같은 응답에 주식분석 유의사항 동의(consent_type STOCK_NOTICE)도 있어 함께 맞춘다(scripts/stockNotice.js).
 * 로그인 중에 단계를 마치면 바로 계정에도 올린다. 서버가 실패해도(테이블 미적용·네트워크) 기기 기록으로 계속 동작한다.
 *
 * 순서대로 잠금은 2026-11-18 에 폐지했다. 어느 단계든 바로 볼 수 있고, '마침' 기록과 '지금 차례' 표시만 남는다.
 * 저장소 접근은 사생활 보호 모드 등에서 실패할 수 있어 모두 try/catch — 실패해도 이번 실행 동안은 동작한다.
 */
import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import aibeesApi from '../aibeesApi.js';
import { assUserSession } from './user-stores.js';
import { allStages, DEFAULT_COURSE, findCourse } from '../training.js';
import { applyAccountStockNotice } from '../stockNotice.js';

const STORAGE_KEY = 'yb-training';
const API_PATH = '/api/v1/training/progress';

const readSaved = () => {
    try {
        const raw = localStorage.getItem(STORAGE_KEY);
        const v = raw ? JSON.parse(raw) : null;
        return v && typeof v === 'object' ? v : {};
    } catch {
        return {};
    }
};

/** 로그인 중이면 user_id, 아니면 null. */
const currentUserId = () => {
    const s = assUserSession();
    return s.user.accessToken ? (s.user.loginInfo?.user_id || null) : null;
};

export const useTrainingStore = defineStore('training', () => {
    const saved = readSaved();
    const done = ref(Array.isArray(saved.done) ? saved.done.filter(k => typeof k === 'string') : []);
    const updatedAt = ref(Number(saved.updatedAt) || 0);
    const owner = ref(saved.owner ?? null);
    // 마지막으로 연 코스(2026-11-24 코스 도입) — '이어서 하기'가 이 코스의 다음 단계를 보여 준다. 기기에만 둔다.
    const lastCourse = ref(findCourse(saved.lastCourse) ? saved.lastCourse : DEFAULT_COURSE);

    const persist = () => {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify({ done: done.value, updatedAt: updatedAt.value, owner: owner.value, lastCourse: lastCourse.value }));
        } catch { /* 저장 실패 — 이번 실행 동안만 기억한다 */ }
    };

    const stages = allStages();
    const doneSet = computed(() => new Set(done.value));
    const isDone = (key) => doneSet.value.has(key);

    // 모든 단계가 처음부터 열려 있다(2026-11-18, 순서대로 잠금 폐지). 없는 단계만 닫힌 것으로 본다.
    const isOpen = (key) => stages.some(s => s.key === key);

    /** 코스 안에서 지금 할 차례: 아직 안 마쳤고 본문이 있는 첫 단계(준비 중 단계는 건너뛴다). 다 마쳤으면 null. */
    const nextIn = (course) => stages.find(s => s.course === course && !isDone(s.key) && s.lesson) ?? null;
    /** 이어서 하기: 마지막으로 연 코스의 다음 단계. 그 코스를 다 마쳤으면 다른 코스에서. */
    const nextStage = computed(() => nextIn(lastCourse.value) ?? stages.find(s => !isDone(s.key) && s.lesson) ?? null);
    const doneIn = (course) => stages.filter(s => s.course === course && isDone(s.key)).length;
    const totalIn = (course) => stages.filter(s => s.course === course).length;
    const useCourse = (course) => {
        if (!findCourse(course) || lastCourse.value === course) return;
        lastCourse.value = course;
        persist();
    };

    // 지금 목차에 있는 단계만 센다(없어진 단계의 기록은 세지 않는다).
    const doneCount = computed(() => stages.filter(s => isDone(s.key)).length);
    const total = stages.length;

    /* ── 계정 저장 ── */
    const serverKeys = (server) => (server?.done ?? []).map(r => r?.stage_key).filter(k => typeof k === 'string');

    const pushToAccount = async (uid, keys) => {
        if (!keys.length) return;
        const { data } = await aibeesApi.post(API_PATH, { stage_keys: keys });
        // 수업 완료 꿀(서버가 단계마다 1번 준다)
        const gained = Number(data?.data?.honeyGained ?? 0);
        if (gained > 0) import('@scripts/stores/honey-store.js').then(({ useHoneyStore }) => useHoneyStore().lessonGained(gained));
        owner.value = uid;
        persist();
    };

    // 이번 실행에서 동기화를 끝낸 user_id. 실패해도 같은 실행에서는 다시 묻지 않는다(이동마다 실패 요청이 쌓이지 않게).
    let syncedFor = null;
    let syncing = null;
    const syncWithAccount = async () => {
        const uid = currentUserId();
        if (!uid) { syncedFor = null; return; }
        if (syncedFor === uid) return;
        if (syncing) return syncing;
        syncing = (async () => {
            try {
                const { data } = await aibeesApi.get(API_PATH);
                const server = data?.data ?? null;
                const remote = serverKeys(server);
                const localMine = owner.value == null || owner.value === uid;
                const local = localMine ? done.value : [];
                const merged = [...new Set([...local, ...remote])];
                const toUpload = local.filter(k => !remote.includes(k));

                if (merged.length !== done.value.length || merged.some(k => !doneSet.value.has(k))) {
                    done.value = merged;
                    updatedAt.value = Date.now();
                }
                owner.value = uid;
                persist();
                if (toUpload.length) await pushToAccount(uid, toUpload);

                await applyAccountStockNotice(uid, server?.stock_notice ?? null);
            } catch (e) {
                console.warn('[training] 계정 동기화 실패 — 이 기기 기록으로 계속', e?.message ?? e);
            } finally {
                syncedFor = uid;
                syncing = null;
            }
        })();
        return syncing;
    };

    /** 단계를 마친다. 본문 없는 단계는 마칠 수 없다. 로그인 중이면 계정에도 올린다. */
    const complete = (key) => {
        const s = stages.find(x => x.key === key);
        if (!s || !s.lesson || !isOpen(key) || isDone(key)) return false;
        done.value = [...done.value, key];
        updatedAt.value = Date.now();
        persist();
        const uid = currentUserId();
        if (uid) pushToAccount(uid, [key]).catch(e => console.warn('[training] 계정 저장 실패 — 기기에는 저장됨', e?.message ?? e));
        return true;
    };

    return { done, updatedAt, owner, isDone, isOpen, nextStage, doneCount, total, complete, syncWithAccount,
        lastCourse, nextIn, doneIn, totalIn, useCourse };
});
