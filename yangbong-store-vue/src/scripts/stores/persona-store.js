/**
 * 성향 설정(유형·화면 모드)과 온보딩 진행 여부.
 * 가입 전에도 쓰므로 이 기기(localStorage)에 두고, 로그인하면 성향 유형을 계정(양봉상회 스키마 user_persona,
 * sql/yangbong/002)으로 옮긴다(기획안 15장 #9 "가입 전에는 기기에 저장, 로그인하면 계정으로 옮긴다").
 * 화면 모드(mode)는 이 기기에만 둔다 — 양봉상회/비밀상회 분리(2026-11-15) 후 양봉상회에는 전문가 모드가 없어진다.
 *
 *   type      : 사용자가 확정한 유형 key. null 이면 아직 안 정함 → 기본 유형으로 보여 준다.
 *   mode      : 'simple' | 'expert'. null 이면 권한 기준 기본값(WORKER_USER 는 전문가, 그 외 간편).
 *   seen      : 온보딩을 한 번이라도 열었는가. 자동으로 여는 건 처음 한 번뿐이다(나가도 다시 끌려가지 않게).
 *   decidedAt : 유형을 확정(또는 건너뛰기)한 시각(ms).
 *   updatedAt : 유형을 마지막으로 바꾼 시각(ms). 계정 값과 비교해 더 최근 쪽을 쓴다.
 *   owner     : 이 기기 값을 마지막으로 계정에 맞춘 user_id. null 이면 로그인 전에 정한 값 →
 *               다음에 로그인하는 계정으로 옮긴다. 다른 계정 것이면 옮기지 않는다(기기를 같이 쓰는 경우).
 *
 * 계정 동기화(syncWithAccount)는 라우터 가드가 로그인 상태의 첫 이동 때 부른다:
 *   - 계정 값이 있고 기기 값보다 최근이거나, 기기 값이 이 계정 것이 아니면 → 계정 값을 쓴다.
 *   - 아니면(기기 값이 더 최근이거나 계정에 없음) → 기기 값을 계정에 올린다.
 * 로그인 중에 바꾸면 바로 계정에도 올린다. 서버가 실패해도(테이블 미적용·네트워크) 기기 값으로 계속 동작한다.
 *
 * 저장소 접근은 사생활 보호 모드 등에서 실패할 수 있어 모두 try/catch — 실패해도 화면은 기본값으로 동작한다.
 */
import { defineStore } from 'pinia';
import { Capacitor } from '@capacitor/core';
import { ref, computed } from 'vue';
import aibeesApi from '../aibeesApi.js';
import { assUserSession } from './user-stores.js';
import { hasRole, WORKER_ROLE } from '../useAccess.js';
import { personaConfig, findType, CUSTOM_KEY } from '../persona.js';
import { normalizeSettings, DEFAULT_SETTINGS } from '../indicators.js';

const CUSTOM_NAME = '나만의 설정';
const normalizeCustom = (c) => ({
    name: String(c?.name ?? '').trim().slice(0, 10) || CUSTOM_NAME,
    settings: normalizeSettings(c?.settings ?? DEFAULT_SETTINGS),
});
/** 화면이 쓰는 유형 모양: {key, name, desc, order, settings}. preset 도 같은 모양으로 맞춘다. */
const toType = (t) => {
    const settings = normalizeSettings(t.settings ?? DEFAULT_SETTINGS);
    return { key: t.key, name: t.name, desc: t.desc ?? '', order: settings.order, settings };
};

const STORAGE_KEY = 'yb-persona';
const API_PATH = '/api/v1/user-options/persona';
const MODES = ['simple', 'expert'];

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

export const usePersonaStore = defineStore('persona', () => {
    const saved = readSaved();
    const type = ref(saved.type ?? null);
    const mode = ref(MODES.includes(saved.mode) ? saved.mode : null);
    const seen = ref(!!saved.seen);
    const decidedAt = ref(saved.decidedAt ?? null);
    const updatedAt = ref(saved.updatedAt ?? saved.decidedAt ?? null);
    const owner = ref(saved.owner ?? null);
    // 나만의 설정 {name, settings}. 이 기기에만 둔다(계정 동기화 대상 아님). 옛 저장값(stopPct 형식)은 기본값으로 바로잡힌다.
    const custom = ref(saved.custom ? normalizeCustom(saved.custom) : null);

    const persist = () => {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify({
                type: type.value, mode: mode.value, seen: seen.value,
                decidedAt: decidedAt.value, updatedAt: updatedAt.value, owner: owner.value, custom: custom.value,
            }));
        } catch { /* 저장 못 해도 이번 실행 동안은 메모리 값으로 동작 */ }
    };

    /** 유형·질문 설정(공통코드 우선, 없으면 내장 기본값). */
    const config = computed(() => personaConfig(assUserSession().access.settings));
    /** 지금 보여 줄 유형(확정 전이면 기본 유형). */
    const presets = computed(() => config.value.types.map(toType));
    const currentType = computed(() => (type.value === CUSTOM_KEY && custom.value)
        ? { key: CUSTOM_KEY, name: custom.value.name, desc: '직접 정한 설정입니다.', order: custom.value.settings.order, settings: custom.value.settings }
        : toType(findType(config.value, type.value)));
    const decided = computed(() => !!type.value);
    const effectiveMode = computed(() => mode.value ?? (hasRole(WORKER_ROLE) ? 'expert' : 'simple'));

    /**
     * 처음 실행할 때 온보딩을 자동으로 열어야 하는가.
     *   - 앱(Capacitor 네이티브)만 연다. 웹은 방문할 때마다(브라우저를 바꾸거나 저장값이 지워질 때마다) 질문이 끼어들면
     *     불편하므로 바로 홈으로 간다 — 웹에서는 홈의 "처음이세요?"로 직접 연다(2026-11-15).
     *   - 매매 사용자(WORKER_USER)는 열지 않는다.
     */
    const needsOnboarding = () => Capacitor.isNativePlatform() && !seen.value && !type.value && !hasRole(WORKER_ROLE);

    /* ── 계정 저장 ── */
    const pushToAccount = async (uid) => {
        if (!type.value || type.value === CUSTOM_KEY) return;   // 나만의 설정은 서버가 모르는 유형 — 이 기기에만
        const { data } = await aibeesApi.put(API_PATH, { persona_type: type.value });
        owner.value = uid;
        if (data?.data?.updated_at) updatedAt.value = data.data.updated_at;
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
                const localMine = !!type.value && (owner.value == null || owner.value === uid);
                if (server?.persona_type && (!localMine || server.updated_at >= (updatedAt.value ?? 0))) {
                    type.value = findType(config.value, server.persona_type).key;
                    updatedAt.value = server.updated_at;
                    owner.value = uid;
                    seen.value = true;
                    persist();
                } else if (localMine) {
                    await pushToAccount(uid);
                }
            } catch (e) {
                console.warn('[persona] 계정 동기화 실패 — 이 기기 값으로 계속', e?.message ?? e);
            } finally {
                syncedFor = uid;
                syncing = null;
            }
        })();
        return syncing;
    };

    /** 값이 바뀌었을 때: 기기에 저장하고, 로그인 중이면 계정에도 올린다. 로그인 전에 바꾼 값은 다음 로그인 계정으로 옮긴다. */
    const changed = () => {
        updatedAt.value = Date.now();
        const uid = currentUserId();
        owner.value = uid;   // 비로그인이면 null
        persist();
        if (uid) pushToAccount(uid).catch(e => console.warn('[persona] 계정 저장 실패 — 기기에는 저장됨', e?.message ?? e));
    };

    const markSeen = () => {
        if (seen.value) return;
        seen.value = true;
        persist();
    };
    /** "이 설정으로 시작" — 사용자가 직접 고른 유형(과 화면 모드)을 확정한다. */
    const decide = (typeKey, modeKey = null) => {
        type.value = findType(config.value, typeKey).key;
        if (MODES.includes(modeKey)) mode.value = modeKey;
        seen.value = true;
        decidedAt.value = Date.now();
        changed();
    };
    /** 나만의 설정을 저장하고 그걸로 확정한다. 기본 유형으로 돌아가도 값은 남아 있어 다시 고를 수 있다. */
    const decideCustom = (c) => {
        custom.value = normalizeCustom(c);
        type.value = CUSTOM_KEY;
        seen.value = true;
        decidedAt.value = Date.now();
        changed();
    };
    /** 건너뛰기 — 기본 유형(균형형)으로 시작한다. */
    const skip = () => decide(config.value.defaultType);
    // 화면 모드는 계정에 올리지 않는다(이 기기에만) — 성향 동기화 기준 시각(updatedAt)도 건드리지 않는다.
    const setMode = (modeKey) => {
        if (!MODES.includes(modeKey)) return;
        mode.value = modeKey;
        persist();
    };

    return { type, mode, seen, decidedAt, updatedAt, owner, custom, decideCustom, config, presets, currentType, decided, effectiveMode,
        needsOnboarding, markSeen, decide, skip, setMode, syncWithAccount };
});
