<template>
    <div id="sell-param-setting">
        <Headers :prop_title="title" />

        <div class="contents">

            <!-- ── 상단 타이틀 ── -->
            <section class="head-desc">
                <div class="head-left">
                    <h2 style="text-align: start;">매도조건 개인화 설정</h2>
                    <p class="sub-text">
                        자동화시스템 매도 판정 파라미터 설정합니다.
                    </p>
                </div>
                <div class="head-right">
                    <button class="btn-refresh" @click="fetchOptions" :disabled="isLoading">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                            stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M23 4v6h-6" /><path d="M1 20v-6h6" />
                            <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10" />
                            <path d="M20.49 15a9 9 0 0 1-14.85 3.36L1 14" />
                        </svg>
                        초기화
                    </button>
                </div>
            </section>

            <!-- ── 판정 우선순위 안내 ── -->
            <section class="priority-bar">
                <span class="pb-title">매도 판정 우선순위</span>
                <ol class="pb-list">
                    <li><b>1</b> 손절</li>
                    <li><b>2</b> 익절</li>
                    <li><b>3</b> 트레일링</li>
                    <li><b>4</b> 타임스탑</li>
                </ol>
                <p class="pb-note">
                    위 순서대로 매도 여부를 확인합니다.<br/>
                    변경한 파라미터는 다음 날부터 반영됩니다.
                </p>
            </section>

            <!-- ── 로딩 스켈레톤 ── -->
            <div v-if="isLoading" class="loader-rows">
                <div v-for="n in 5" :key="n" class="skeleton-row"></div>
            </div>

            <form v-else class="setting-form" @submit.prevent="save">

                <!-- ════════ A ~ D 그룹 카드 ════════ -->
                <section v-for="g in GROUPS" :key="g.id" class="setting-card">
                    <header class="card-head">
                        <div class="ch-left">
                            <span class="prio-badge">{{ g.priority }}</span>
                            <h3>{{ g.title }}</h3>
                        </div>

                        <!-- 그룹 마스터 토글 -->
                        <button v-if="g.master" type="button"
                            :class="['toggle-btn', isOn(g.master) ? 'active' : 'inactive']"
                            role="switch" :aria-checked="isOn(g.master)"
                            @click="toggleBool(g.master)">
                            <span class="toggle-knob"></span>
                        </button>
                    </header>
                    <span class="card-desc" v-html="g.desc"></span>

                    <div class="field-list">
                        <div v-for="f in g.fields" :key="f.k"
                            :class="['field-row', { disabled: isDisabled(f.k) }]">

                            <!-- 라벨 줄 -->
                            <div class="fr-head">
                                <label :for="f.k">
                                    {{ f.label }}
                                    <span v-if="f.unit" class="fr-unit">({{ f.unit }})</span>
                                </label>
                                <div class="fr-right">
                                    <span class="fr-def">
                                        기본 {{ defDisplay(f) }}<template v-if="f.unit === '%' && f.def !== null">%</template>
                                    </span>
                                    <button v-if="f.type !== 'bool' && f.type !== 'enum'" type="button"
                                        class="btn-null" :title="f.def === null ? '비워서 미사용(null)' : '기본값 따름(null)'"
                                        :disabled="isDisabled(f.k)"
                                        @click="form[f.k] = ''">{{ f.nullLabel ?? '기본값' }}</button>
                                </div>
                            </div>

                            <!-- 컨트롤 -->
                            <!-- bool -->
                            <div v-if="f.type === 'bool'" class="fr-ctrl bool-ctrl">
                                <button type="button"
                                    :class="['toggle-btn', isOn(f.k) ? 'active' : 'inactive']"
                                    role="switch" :aria-checked="isOn(f.k)"
                                    :disabled="isDisabled(f.k)"
                                    @click="toggleBool(f.k)">
                                    <span class="toggle-knob"></span>
                                </button>
                                <span class="bool-text">{{ isOn(f.k) ? '사용' : '미사용' }}</span>
                            </div>

                            <!-- enum(radio) -->
                            <div v-else-if="f.type === 'enum'" class="fr-ctrl enum-ctrl">
                                <label v-for="o in f.options" :key="o.v"
                                    :class="['radio-chip', { on: form[f.k] === o.v, off: isDisabled(f.k) }]">
                                    <input type="radio" :name="f.k" :value="o.v"
                                        v-model="form[f.k]" :disabled="isDisabled(f.k)" />
                                    {{ o.label }}
                                </label>
                            </div>

                            <!-- stepper (정수 소범위) -->
                            <div v-else-if="f.ui === 'stepper'" class="fr-ctrl stepper-ctrl">
                                <button type="button" class="st-btn" :disabled="isDisabled(f.k)"
                                    @click="bump(f, -1)">−</button>
                                <input :id="f.k" type="number" class="st-input"
                                    :value="form[f.k]" @input="onNumInput(f, $event)"
                                    :min="f.min" :max="f.max" :step="f.step"
                                    :placeholder="String(defDisplay(f))"
                                    :disabled="isDisabled(f.k)" inputmode="numeric" />
                                <button type="button" class="st-btn" :disabled="isDisabled(f.k)"
                                    @click="bump(f, 1)">+</button>
                                <span class="st-unit">{{ f.unit }}</span>
                            </div>

                            <!-- slider + number (양방향 동기화) -->
                            <div v-else class="fr-ctrl slider-ctrl">
                                <input type="range" class="sl-range"
                                    :value="sliderVal(f)" @input="onNumInput(f, $event)"
                                    :min="f.min" :max="sliderMax(f)" :step="f.step"
                                    :disabled="isDisabled(f.k)" />
                                <div class="sl-num">
                                    <input :id="f.k" type="number"
                                        :value="form[f.k]" @input="onNumInput(f, $event)"
                                        :min="f.min" :max="f.max" :step="f.step"
                                        :placeholder="String(defDisplay(f))"
                                        :disabled="isDisabled(f.k)" inputmode="decimal" />
                                    <span class="sl-unit">{{ f.unit }}</span>
                                </div>
                            </div>

                            <span v-if="f.hint" class="field-hint">{{ f.hint }}</span>
                            <span v-if="errors[f.k]" class="field-error">{{ errors[f.k] }}</span>
                        </div>

                        <!-- 백엔드 미지원 항목(변수화 예정) -->
                        <!-- <div v-if="g.id === 'A'" class="field-row disabled pending">
                            <div class="fr-head">
                                <label>ema20 위면 손절 보류</label>
                                <span class="fr-def">기본 ON</span>
                            </div>
                            <div class="fr-ctrl bool-ctrl">
                                <button type="button" class="toggle-btn active" disabled>
                                    <span class="toggle-knob"></span>
                                </button>
                                <span class="bool-text">사용</span>
                            </div>
                            <span class="field-hint">
                                현재 전략 코드에 고정되어 있습니다. 조정하려면 백엔드
                                <code>s1_stop_require_below_ema20</code> 컬럼 신설이 필요합니다.
                            </span>
                        </div> -->
                    </div>
                </section>

                <!-- ════════ 미리보기 ════════ -->
                <section class="setting-card preview-card">
                    <header class="card-head">
                        <div class="ch-left">
                            <span class="prio-badge preview">SIM</span>
                            <h3>라인 미리보기</h3>
                        </div>
                    </header>
                    <span class="card-desc">가상의 진입가 기준으로 현재 설정이 만들 라인을 계산합니다. 저장 전 값으로 즉시 반영됩니다.</span>

                    <div class="pv-inputs">
                        <div class="pv-field">
                            <label>가상 진입가</label>
                            <input type="number" v-model="preview.entry" min="0" step="10" inputmode="numeric" />
                        </div>
                        <div class="pv-field">
                            <label>ATR (선택)</label>
                            <input type="number" v-model="preview.atr" min="0" step="any"
                                placeholder="미입력 시 대체 % 사용" inputmode="decimal" />
                        </div>
                    </div>

                    <ul class="pv-lines">
                        <li>
                            <span class="pl-label down-c">손절 stop_price</span>
                            <span class="pl-value">{{ fmtWon(lines.stop) }}</span>
                            <span class="pl-sub">진입가 −{{ pctText('s1_stop_loss_pct') }}</span>
                        </li>
                        <li>
                            <span class="pl-label up-c">익절 target_price</span>
                            <span class="pl-value">{{ fmtWon(lines.target) }}</span>
                            <span class="pl-sub">진입가 +{{ pctText('s1_take_profit_pct') }}</span>
                        </li>
                        <li :class="{ muted: !isOn('s1_use_trailing') }">
                            <span class="pl-label">트레일링 trail_line</span>
                            <span class="pl-value">{{ isOn('s1_use_trailing') ? fmtWon(lines.trail) : '미사용' }}</span>
                            <span class="pl-sub">{{ lines.trailBasisText }}</span>
                        </li>
                    </ul>
                    <p class="pv-note">
                        고점(peak)은 활성화 수익 {{ pctText('s1_trail_activate_pct') }} 도달 시점을 가정했습니다.
                        실제 고점은 <b>매수 시점부터 실시간 체결가로 추적</b>되며(장중 메모리 · 장 종료 시 저장),
                        종가·장중 구분 없이 단일 기준을 씁니다.
                    </p>
                </section>

                <!-- ════════ E. 실행·안전 (read-only) ════════ -->
                <section class="setting-card exec-card">
                    <header class="card-head">
                        <div class="ch-left">
                            <span class="prio-badge exec">ENV</span>
                            <h3>실행 · 안전</h3>
                        </div>
                    </header>
                    <span class="card-desc">
                        전략 판정이 아니라 <b>주문 실행/재시도 정책</b>입니다. 현재 worker 환경변수로만 주입되며
                        화면에서 수정할 수 없습니다. 변경하려면 worker 재시작이 필요합니다.
                    </span>

                    <div class="exec-list">
                        <div v-for="e in EXEC_FIELDS" :key="e.k" class="exec-row">
                            <div class="ex-left">
                                <span class="ex-label">{{ e.label }}</span>
                                <span class="ex-hint">{{ e.hint }}</span>
                            </div>
                            <div class="ex-right">
                                <span class="ex-value">{{ e.def }}<i>{{ e.unit }}</i></span>
                                <span class="ex-key">{{ e.k }}</span>
                            </div>
                        </div>
                    </div>
                </section>

                <!-- ════════ 저장 바 ════════ -->
                <div class="save-bar">
                    <span class="dirty-note" v-if="isDirty">변경된 항목 {{ dirtyCount }}건</span>
                    <span class="dirty-note clean" v-else>변경 사항 없음</span>
                    <button type="button" class="btn-reset" @click="resetForm" :disabled="!isDirty || isSaving">되돌리기</button>
                    <button type="submit" class="btn-save" :disabled="!isDirty || isSaving || hasError">
                        {{ isSaving ? '저장 중…' : '저장' }}
                    </button>
                </div>
            </form>
        </div>
    </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue';
import aibeesApi from '@scripts/aibeesApi.js';
import mariaToast from '@scripts/mariaToast.js';

const title = ref('매도 설정');

/* ═══════════════════════════════════════════════════════════
 * 필드 메타
 *  - def  : 전략 클래스 기본값(내부 저장 단위. % 계열은 소수)
 *  - unit : '%' 이면 화면 표시는 ×100, 전송은 ÷100
 *  - min/max/step 은 화면 표시 단위 기준
 * ═══════════════════════════════════════════════════════════ */
const GROUPS = [
    {
        id: 'A', priority: 1, title: '손실 감수매도 기준',
        desc: '일정% 손절 또는 OBV 데드크로스(세력 청산 신호). <br/>가장 먼저 평가되는 최우선 조건입니다.',
        fields: [
            {
                k: 's1_stop_loss_pct', label: '손실', unit: '%', type: 'pct', def: 0.05,
                min: 2, max: 15, step: 0.5,
                hint: '진입가 대비 −N% 하회 시 전량 손절합니다.',
            },
            {
                k: 's1_obv_dead_min_bars', label: 'OBV 데드크로스 무시 봉 갯수', unit: '', type: 'int', def: 5,
                min: 0, max: 20, step: 1, ui: 'stepper',
                hint: '진입 후 이 봉수 이내의 OBV 데드크로스는 노이즈로 보고 무시합니다.',
            },
        ],
    },
    {
        id: 'B', priority: 2, title: '이익 실현매도 기준',
        desc: '진입가 대비 목표 수익 도달 시 전량 익절합니다.',
        fields: [
            {
                k: 's1_take_profit_pct', label: '이익', unit: '%', type: 'pct', def: 0.30,
                min: 5, max: 100, step: 5,
                hint: '진입가 대비 +N% 도달 시 전량 익절합니다.',
            },
        ],
    },
    {
        id: 'C', priority: 3, title: '트레일링 스탑 (Chandelier)',
        desc: '매수 시점부터 실시간 체결가로 고점을 추적하고, 그 고점에서 설정폭만큼 하락하면 청산합니다. 마스터 토글을 끄면 하위 항목이 비활성화됩니다.',
        master: 's1_use_trailing',
        fields: [
            {
                k: 's1_trail_activate_pct', label: '활성화 수익', unit: '%', type: 'pct', def: 0.08,
                min: 0, max: 50, step: 1,
                hint: '고점 수익이 이 값 이상일 때만 트레일링이 켜집니다.',
            },
            {
                k: 's1_k_trail_atr', label: 'ATR 배수 (k)', unit: '배', type: 'float', def: 3.0,
                min: 1, max: 6, step: 0.5,
                hint: '작을수록 타이트해서 빨리 매도합니다. 종목별 튜닝 포인트.',
            },
            {
                k: 's1_trail_floor_pct', label: 'ATR 미산출 대체', unit: '%', type: 'pct', def: 0.10,
                min: 3, max: 30, step: 1,
                hint: 'ATR을 구하지 못할 때만 쓰는 fallback (고점 −N%).',
            },
            {
                k: 's1_trail_drawdown_pct', label: '고점 대비 하락폭', unit: '%', type: 'pct',
                def: null, nullLabel: '미사용', nullSlider: 5,
                min: 1, max: 30, step: 0.5,
                hint: '고점에서 이 비율만큼 빠지면 청산합니다. 비우면(미사용) ATR 라인만 씁니다.',
            },
            {
                k: 's1_trail_dual', label: 'ATR 라인과 이중 감시', type: 'bool', def: 1,
                hint: 'ON = ATR 라인과 하락폭 라인 중 먼저 닿는 쪽에서 매도. OFF = 하락폭 라인 단독.',
            },
        ],
    },
    {
        id: 'D', priority: 4, title: '동적 타임스탑 (Time Stop)',
        desc: '보유 봉수 한도에 도달하면 평가를 시작합니다. 추세가 살아있으면 매도를 보류할 수 있습니다.',
        fields: [
            {
                k: 's1_max_hold_bars', label: '보유 한도', unit: '봉', type: 'int', def: 12,
                min: 3, max: 60, step: 1,
                hint: '이 봉수에 도달하면 타임스탑 평가를 시작합니다.',
            },
            {
                k: 's1_time_stop_extend', label: '추세 생존 시 연장', type: 'bool', def: 1,
                hint: '수익 > 밴드 & ema20 위 & grace봉 내 신고가면 매도를 보류하고 트레일/손절에 위임합니다.',
            },
            {
                k: 's1_time_stop_band', label: '정체 판정 수익밴드', unit: '%', type: 'pct', def: 0.02,
                min: 0, max: 10, step: 0.5,
                hint: '이 수익 이하면 정체로 보고 타임스탑을 실행합니다.',
            },
            {
                k: 's1_time_stop_grace', label: '신고가 grace 봉수', unit: '봉', type: 'int', def: 3,
                min: 0, max: 10, step: 1, ui: 'stepper',
                hint: '최근 이 봉수 이내에 신고가를 갱신해야 연장을 허용합니다.',
            },
            {
                k: 's1_max_hold_bars_hard', label: '절대 보유 한도', unit: '봉', type: 'int', def: 20,
                min: 3, max: 120, step: 1,
                hint: '연장을 포함한 절대 상한. 보유 한도보다 크거나 같아야 합니다.',
            },
        ],
    },
];

/* E 그룹 — worker env (read-only) */
const EXEC_FIELDS = [
    {
        k: 'SELL_RETRY_COOLDOWN_SEC', label: '매도 실패 재시도 쿨다운', def: 60, unit: '초',
        hint: '매도 주문 실패 시 재시도까지의 대기 시간 (폭주 방지)',
    },
    {
        k: 'SELL_MAX_FAILS', label: '연속 실패 자동 비활성 임계', def: 5, unit: '회',
        hint: '연속 실패가 이 횟수에 도달하면 해당 종목을 자동 비활성화',
    },
];

/* 마스터 토글은 폼 필드로도 관리해야 하므로 별도 등록 */
const MASTER_FIELDS = [{ k: 's1_use_trailing', type: 'bool', def: 1 }];

const ALL_FIELDS = [
    ...MASTER_FIELDS,
    ...GROUPS.flatMap(g => g.fields),
];
const FIELD_MAP = Object.fromEntries(ALL_FIELDS.map(f => [f.k, f]));
const ALL_KEYS = ALL_FIELDS.map(f => f.k);

/* 조건부 비활성화 규칙
 *  - 값이 문자열이면 "해당 bool 필드가 OFF일 때 비활성"
 *  - 값이 함수면 true 반환 시 비활성 (복합 조건용)
 */
const DISABLE_RULES = {
    s1_trail_activate_pct: 's1_use_trailing',
    s1_k_trail_atr: 's1_use_trailing',
    s1_trail_floor_pct: 's1_use_trailing',
    s1_trail_drawdown_pct: 's1_use_trailing',
    // 이중감시 스위치는 하락폭이 실제로 설정됐을 때만 의미가 있다
    s1_trail_dual: () => !isOn('s1_use_trailing') || isBlank('s1_trail_drawdown_pct'),
    s1_time_stop_band: 's1_time_stop_extend',
    s1_time_stop_grace: 's1_time_stop_extend',
};

/* ═══════════════ 폼 상태 ═══════════════
 * form[k] 는 "화면 표시 단위" 문자열/숫자.
 *  - pct  : 5   (=0.05)
 *  - bool : 1 / 0
 *  - enum : 'close'
 *  - ''   : null (기본값 따름)
 */
const form = reactive({});
let original = {};
const isLoading = ref(true);
const isSaving = ref(false);

const blankForm = () => {
    const o = {};
    ALL_KEYS.forEach(k => { o[k] = ''; });
    // bool / enum 은 null 개념을 쓰지 않고 기본값으로 시작
    ALL_FIELDS.forEach(f => {
        if (f.type === 'bool' || f.type === 'enum') o[f.k] = f.def;
    });
    return o;
};

/* 표시 단위 ↔ 저장 단위 */
// 라벨/placeholder 용 — def 가 null 인 필드는 '미사용' 같은 텍스트로 표기
const defDisplay = (f) => {
    if (f.def === null || f.def === undefined) return f.nullLabel ?? '없음';
    return f.type === 'pct' ? +(f.def * 100).toFixed(4) : f.def;
};
// slider/stepper 의 숫자 fallback — def 가 null 이면 nullSlider(없으면 min)
const defNum = (f) => {
    if (f.def === null || f.def === undefined) return f.nullSlider ?? f.min ?? 0;
    return f.type === 'pct' ? +(f.def * 100).toFixed(4) : f.def;
};
const toDisplay = (f, raw) => {
    if (raw === null || raw === undefined || raw === '') return f.type === 'bool' || f.type === 'enum' ? f.def : '';
    if (f.type === 'pct') return +(Number(raw) * 100).toFixed(4);
    if (f.type === 'bool') return Number(raw) ? 1 : 0;
    if (f.type === 'enum') return String(raw);
    return Number(raw);
};
const toApi = (f, disp) => {
    if (f.type === 'enum') return disp === '' || disp === null ? null : String(disp);
    if (f.type === 'bool') return Number(disp) ? 1 : 0;
    if (disp === '' || disp === null || disp === undefined) return null;
    if (f.type === 'pct') return +(Number(disp) / 100).toFixed(6);
    if (f.type === 'int') return parseInt(disp, 10);
    return Number(disp);
};

/* ═══════════════ 조회 ═══════════════ */
const fetchOptions = async () => {
    isLoading.value = true;
    Object.assign(form, blankForm());
    try {
        const { data } = await aibeesApi.get('/api/v1/strategy/options');
        const d = data.data ?? {};
        ALL_FIELDS.forEach(f => {
            if (d[f.k] !== undefined) form[f.k] = toDisplay(f, d[f.k]);
        });
    } catch (e) {
        console.error('[SellParamSetting] 조회 실패', e);
    } finally {
        original = JSON.parse(JSON.stringify(form));
        isLoading.value = false;
    }
};
onMounted(fetchOptions);

/* ═══════════════ 컨트롤 헬퍼 ═══════════════ */
const isOn = (k) => Number(form[k]) === 1;
const toggleBool = (k) => {
    if (isDisabled(k)) return;
    form[k] = isOn(k) ? 0 : 1;
};
const isBlank = (k) => form[k] === '' || form[k] === null || form[k] === undefined;
const isDisabled = (k) => {
    const dep = DISABLE_RULES[k];
    if (!dep) return false;
    return typeof dep === 'function' ? dep() : !isOn(dep);
};

const clamp = (f, v) => Math.min(f.max, Math.max(f.min, v));

const onNumInput = (f, ev) => {
    const raw = ev.target.value;
    if (raw === '') { form[f.k] = ''; return; }
    const n = Number(raw);
    if (Number.isNaN(n)) return;
    form[f.k] = f.type === 'int' ? Math.round(n) : n;
};

const bump = (f, dir) => {
    if (isDisabled(f.k)) return;
    const cur = isBlank(f.k) ? defNum(f) : Number(form[f.k]);
    form[f.k] = clamp(f, cur + dir * f.step);
};

const sliderVal = (f) => (isBlank(f.k) ? defNum(f) : Number(form[f.k]));
// 절대 보유 한도는 보유 한도보다 작을 수 없으므로 슬라이더 상한은 메타 그대로 두고 검증으로 처리
const sliderMax = (f) => f.max;

/* ═══════════════ 검증 ═══════════════ */
const errors = computed(() => {
    const e = {};
    ALL_FIELDS.forEach(f => {
        if (f.type === 'bool' || f.type === 'enum') return;
        const v = form[f.k];
        if (v === '' || v === null) return;
        if (Number(v) < f.min || Number(v) > f.max) {
            e[f.k] = `허용 범위: ${f.min} ~ ${f.max}${f.unit === '%' ? '%' : ''}`;
        }
    });

    const hold = form.s1_max_hold_bars === '' ? FIELD_MAP.s1_max_hold_bars.def : Number(form.s1_max_hold_bars);
    const hard = form.s1_max_hold_bars_hard === '' ? FIELD_MAP.s1_max_hold_bars_hard.def : Number(form.s1_max_hold_bars_hard);
    if (hard < hold) {
        e.s1_max_hold_bars_hard = `절대 보유 한도(${hard}봉)는 보유 한도(${hold}봉) 이상이어야 합니다.`;
    }
    return e;
});
const hasError = computed(() => Object.keys(errors.value).length > 0);

/* ═══════════════ diff / 저장 ═══════════════ */
const buildDiff = () => {
    const diff = {};
    ALL_FIELDS.forEach(f => {
        if (String(form[f.k]) !== String(original[f.k])) {
            diff[f.k] = toApi(f, form[f.k]);
        }
    });
    return diff;
};
const isDirty = computed(() => Object.keys(buildDiff()).length > 0);
const dirtyCount = computed(() => Object.keys(buildDiff()).length);

const resetForm = () => Object.assign(form, JSON.parse(JSON.stringify(original)));

const save = async () => {
    if (hasError.value) {
        mariaToast.error('입력값을 확인해 주세요.');
        return;
    }
    const payload = buildDiff();
    if (Object.keys(payload).length === 0) {
        mariaToast.info('변경된 항목이 없습니다.');
        return;
    }
    isSaving.value = true;
    try {
        await aibeesApi.patch('/api/v1/strategy/options', payload);
        original = JSON.parse(JSON.stringify(form));
        mariaToast.success('저장되었습니다. 다음 daily 평가부터 라인에 반영됩니다.');
    } catch (e) {
        console.error('[SellParamSetting] 저장 실패', e);
    } finally {
        isSaving.value = false;
    }
};

/* ═══════════════ 미리보기 ═══════════════ */
const preview = reactive({ entry: 10000, atr: '' });

// 화면값(빈값이면 기본값) → 소수 비율. def 가 null 인 필드는 비었으면 null 반환.
const rate = (k) => {
    const f = FIELD_MAP[k];
    if (isBlank(k) && (f.def === null || f.def === undefined)) return null;
    const disp = isBlank(k) ? defNum(f) : Number(form[k]);
    return f.type === 'pct' ? disp / 100 : disp;
};
const pctText = (k) => {
    const r = rate(k);
    return r === null ? '미사용' : `${(r * 100).toFixed(2)}%`;
};

/* KospiStrategy1._trail_line_of 와 동일한 조합 규칙:
 *   drawdown 미설정        → ATR 라인 단독
 *   설정 + trail_dual=ON   → max(ATR 라인, drawdown 라인)  ← 먼저 닿는 쪽
 *   설정 + trail_dual=OFF  → drawdown 라인 단독
 */
const lines = computed(() => {
    const entry = Number(preview.entry) || 0;
    const atr = preview.atr === '' ? null : Number(preview.atr);

    const stop = entry * (1 - rate('s1_stop_loss_pct'));
    const target = entry * (1 + rate('s1_take_profit_pct'));
    const peak = entry * (1 + rate('s1_trail_activate_pct'));

    let atrLine, atrText;
    if (atr && atr > 0) {
        atrLine = peak - rate('s1_k_trail_atr') * atr;
        atrText = `ATR 라인 = 고점 ${fmtWon(peak)} − ${rate('s1_k_trail_atr')}×ATR(${atr})`;
    } else {
        atrLine = peak * (1 - rate('s1_trail_floor_pct'));
        atrText = `ATR 미입력 → 대체 라인 = 고점 ${fmtWon(peak)} −${(rate('s1_trail_floor_pct') * 100).toFixed(2)}%`;
    }

    const dd = rate('s1_trail_drawdown_pct');
    if (dd === null) {
        return { stop, target, trail: atrLine, atrLine, ddLine: null, trailBasisText: atrText };
    }

    const ddLine = peak * (1 - dd);
    const ddText = `하락폭 라인 = 고점 ${fmtWon(peak)} −${(dd * 100).toFixed(2)}%`;

    if (isOn('s1_trail_dual')) {
        const picked = Math.max(atrLine, ddLine);
        return {
            stop, target, trail: picked, atrLine, ddLine,
            trailBasisText: `${atrText} / ${ddText} → 이중감시 max = ${fmtWon(picked)}`,
        };
    }
    return { stop, target, trail: ddLine, atrLine, ddLine, trailBasisText: `${ddText} (단독)` };
});

/* ═══════════════ 포맷 ═══════════════ */
function fmtWon(v) {
    if (v === null || v === undefined || Number.isNaN(Number(v))) return '-';
    return Math.round(Number(v)).toLocaleString() + '원';
}
</script>

<style scoped>
#sell-param-setting {
    min-height: 100vh;
    background: #f4f6f9;
}

.contents {
    max-width: 760px;
    margin: 0 auto;
    padding: 16px 14px 96px;
    box-sizing: border-box;
}

/* ── 상단 ── */
.head-desc {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
    padding: 8px 4px 16px;
}

.head-desc h2 {
    margin: 0;
    font-size: 1.25rem;
    font-weight: 700;
    color: #1f2329;
}

.head-desc .sub-text {
    margin: 6px 0 0;
    font-size: 0.85rem;
    color: #6b7280;
    line-height: 1.4;
}

.btn-refresh {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    height: 32px;
    padding: 0 12px;
    border: 1px solid #d6dbe1;
    border-radius: 999px;
    background: #fff;
    color: #4b5563;
    font-size: 0.78rem;
    font-weight: 600;
    cursor: pointer;
    white-space: nowrap;
}

.btn-refresh:hover:not(:disabled) {
    border-color: #2db400;
    color: #2db400;
}

/* ── 우선순위 안내 ── */
.priority-bar {
    background: #eef7ea;
    border: 1px solid #cfe6c2;
    border-radius: 14px;
    padding: 14px 16px;
    margin-bottom: 14px;
}

.pb-title {
    font-size: 0.78rem;
    font-weight: 700;
    color: #2db400;
}

.pb-list {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: center;
    gap: 6px;
    list-style: none;
    margin: 8px 0 0;
    padding: 0;
}

.pb-list li {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    background: #fff;
    border: 1px solid #cfe6c2;
    border-radius: 999px;
    padding: 4px 10px;
    font-size: 0.8rem;
    font-weight: 600;
    color: #3b4149;
}

.pb-list li + li::before {
    content: '›';
    color: #9bbf8a;
    margin-right: 2px;
}

.pb-list li b {
    display: grid;
    place-items: center;
    width: 16px;
    height: 16px;
    border-radius: 50%;
    background: #2db400;
    color: #fff;
    font-size: 0.65rem;
}

.pb-note {
    margin: 10px 0 0;
    font-size: 0.76rem;
    color: #5c6b52;
    line-height: 1.5;
}

/* ── 스켈레톤 ── */
.loader-rows {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.skeleton-row {
    height: 96px;
    border-radius: 14px;
    background: linear-gradient(90deg, #eef1f5 25%, #f7f9fb 37%, #eef1f5 63%);
    background-size: 400% 100%;
    animation: shimmer 1.2s ease-in-out infinite;
}

@keyframes shimmer {
    0% { background-position: 100% 50%; }
    100% { background-position: 0 50%; }
}

/* ── 카드 ── */
.setting-card {
    background: #fff;
    border: 1px solid #e5e8ec;
    border-radius: 14px;
    padding: 18px 18px 20px;
    margin-bottom: 14px;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
}

.card-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
}

.ch-left {
    display: flex;
    align-items: center;
    gap: 8px;
}

.card-head h3 {
    margin: 0;
    font-size: 1rem;
    font-weight: 700;
    color: #2db400;
}

.prio-badge {
    display: grid;
    place-items: center;
    min-width: 22px;
    height: 22px;
    padding: 0 6px;
    border-radius: 7px;
    background: #2db400;
    color: #fff;
    font-size: 0.72rem;
    font-weight: 700;
}

.prio-badge.preview { background: #4b7bec; }
.prio-badge.exec { background: #e8873a; }

.card-desc {
    display: block;
    margin-top: 6px;
    font-size: 0.78rem;
    text-align: start;
    color: #8a929c;
    line-height: 1.45;
}

/* ── 필드 ── */
.field-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
    margin-top: 14px;
}

.field-row {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 12px 0;
    border-top: 1px solid #f0f2f5;
}

.field-row:first-child {
    border-top: 0;
    padding-top: 4px;
}

.field-row.disabled {
    opacity: 0.45;
}

.field-row.pending {
    background: #fbfcfd;
    border-radius: 10px;
    padding: 12px;
}

.fr-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
}

.fr-head label {
    font-size: 0.88rem;
    font-weight: 600;
    color: #3b4149;
}

.fr-unit {
    font-weight: 500;
    color: #9aa3ad;
    font-size: 0.8rem;
}

.fr-right {
    display: flex;
    align-items: center;
    gap: 8px;
}

.fr-def {
    font-size: 0.72rem;
    color: #b3bac2;
    white-space: nowrap;
}

.btn-null {
    height: 22px;
    padding: 0 8px;
    border: 1px solid #e0e4e9;
    border-radius: 6px;
    background: #fff;
    color: #8a929c;
    font-size: 0.68rem;
    cursor: pointer;
}

.btn-null:hover:not(:disabled) {
    border-color: #2db400;
    color: #2db400;
}

/* slider */
.slider-ctrl {
    display: flex;
    align-items: center;
    gap: 12px;
}

.sl-range {
    flex: 1 1 auto;
    -webkit-appearance: none;
    appearance: none;
    height: 4px;
    border-radius: 999px;
    background: #e3e7ec;
    outline: none;
}

.sl-range::-webkit-slider-thumb {
    -webkit-appearance: none;
    appearance: none;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background: #2db400;
    border: 2px solid #fff;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.25);
    cursor: pointer;
}

.sl-range::-moz-range-thumb {
    width: 16px;
    height: 16px;
    border-radius: 50%;
    background: #2db400;
    border: 2px solid #fff;
    cursor: pointer;
}

.sl-range:disabled::-webkit-slider-thumb { background: #b6bcc4; }

.sl-num {
    flex: 0 0 auto;
    display: flex;
    align-items: center;
    gap: 4px;
}

.sl-num input {
    width: 76px;
    height: 34px;
    box-sizing: border-box;
    padding: 0 8px;
    border: 1px solid #d6dbe1;
    border-radius: 8px;
    font-size: 0.88rem;
    text-align: right;
    color: #1f2329;
    background: #fff;
}

.sl-num input:focus {
    outline: none;
    border-color: #2db400;
    box-shadow: 0 0 0 3px rgba(45, 180, 0, 0.12);
}

.sl-unit,
.st-unit {
    font-size: 0.78rem;
    color: #8a929c;
    min-width: 16px;
}

/* stepper */
.stepper-ctrl {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
}

.st-btn {
    width: 34px;
    height: 34px;
    border: 1px solid #d6dbe1;
    border-radius: 8px;
    background: #fff;
    color: #3b4149;
    font-size: 1rem;
    cursor: pointer;
}

.st-btn:hover:not(:disabled) {
    border-color: #2db400;
    color: #2db400;
}

.st-input {
    width: 68px;
    height: 34px;
    box-sizing: border-box;
    padding: 0 8px;
    border: 1px solid #d6dbe1;
    border-radius: 8px;
    text-align: center;
    font-size: 0.88rem;
    color: #1f2329;
}

.st-input:focus {
    outline: none;
    border-color: #2db400;
}

/* bool */
.bool-ctrl {
    display: flex;
    align-items: center;
    gap: 10px;
}

.bool-text {
    font-size: 0.8rem;
    color: #6b7280;
}

.toggle-btn {
    flex: 0 0 auto;
    width: 46px;
    height: 26px;
    border-radius: 999px;
    border: 0;
    position: relative;
    cursor: pointer;
    transition: background 0.18s;
    background: #cfd6de;
}

.toggle-btn.active { background: #2db400; }

.toggle-knob {
    position: absolute;
    top: 3px;
    left: 3px;
    width: 20px;
    height: 20px;
    background: #fff;
    border-radius: 50%;
    transition: transform 0.18s;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
}

.toggle-btn.active .toggle-knob { transform: translateX(20px); }

/* enum */
.enum-ctrl {
    display: flex;
    gap: 8px;
}

.radio-chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 7px 14px;
    border: 1px solid #d6dbe1;
    border-radius: 999px;
    font-size: 0.82rem;
    color: #4b5563;
    cursor: pointer;
    background: #fff;
}

.radio-chip input { accent-color: #2db400; }

.radio-chip.on {
    border-color: #2db400;
    background: rgba(45, 180, 0, 0.07);
    color: #2db400;
    font-weight: 600;
}

.radio-chip.off { cursor: not-allowed; }

.field-hint {
    font-size: 0.74rem;
    color: #9aa3ad;
    line-height: 1.4;
}

.field-hint code {
    background: #f0f2f5;
    border-radius: 4px;
    padding: 1px 4px;
    font-size: 0.72rem;
}

.field-error {
    font-size: 0.74rem;
    color: #e03131;
    font-weight: 600;
}

/* ── 미리보기 ── */
.preview-card {
    border-color: #d6e0f7;
    background: #fbfcff;
}

.preview-card .card-head h3 { color: #4b7bec; }

.pv-inputs {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
    margin-top: 14px;
}

.pv-field {
    display: flex;
    flex-direction: column;
    gap: 6px;
}

.pv-field label {
    font-size: 0.8rem;
    font-weight: 600;
    color: #3b4149;
}

.pv-field input {
    height: 38px;
    box-sizing: border-box;
    padding: 0 10px;
    border: 1px solid #d6dbe1;
    border-radius: 9px;
    font-size: 0.88rem;
    text-align: right;
    background: #fff;
}

.pv-field input:focus {
    outline: none;
    border-color: #4b7bec;
    box-shadow: 0 0 0 3px rgba(75, 123, 236, 0.12);
}

.pv-lines {
    list-style: none;
    margin: 14px 0 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.pv-lines li {
    display: grid;
    grid-template-columns: 1fr auto;
    grid-template-areas: 'label value' 'sub sub';
    gap: 2px 10px;
    background: #fff;
    border: 1px solid #e5e8ec;
    border-radius: 10px;
    padding: 10px 12px;
}

.pv-lines li.muted { opacity: 0.5; }

.pl-label {
    grid-area: label;
    font-size: 0.82rem;
    font-weight: 600;
    color: #3b4149;
}

.pl-value {
    grid-area: value;
    font-size: 0.95rem;
    font-weight: 700;
    color: #1f2329;
}

.pl-sub {
    grid-area: sub;
    font-size: 0.72rem;
    color: #9aa3ad;
}

.up-c { color: #e03131; }
.down-c { color: #1c7ed6; }

.pv-note {
    margin: 10px 0 0;
    font-size: 0.73rem;
    color: #9aa3ad;
}

/* ── E 실행·안전 ── */
.exec-card {
    border-color: #f0d9c2;
    background: #fffcf8;
}

.exec-card .card-head h3 { color: #e8873a; }

.exec-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-top: 14px;
}

.exec-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    background: #fff;
    border: 1px solid #f0e2d2;
    border-radius: 10px;
    padding: 11px 13px;
}

.ex-left {
    display: flex;
    flex-direction: column;
    gap: 3px;
}

.ex-label {
    font-size: 0.85rem;
    font-weight: 600;
    color: #3b4149;
}

.ex-hint {
    font-size: 0.72rem;
    color: #a89b8d;
    line-height: 1.35;
}

.ex-right {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 2px;
}

.ex-value {
    font-size: 1rem;
    font-weight: 700;
    color: #1f2329;
}

.ex-value i {
    font-style: normal;
    font-size: 0.75rem;
    font-weight: 500;
    color: #8a929c;
    margin-left: 2px;
}

.ex-key {
    font-size: 0.66rem;
    color: #c2b5a6;
    font-family: ui-monospace, Menlo, monospace;
}

/* ── 저장 바 ── */
.save-bar {
    position: sticky;
    bottom: 0;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 12px 14px;
    margin: 4px -14px 0;
    background: rgba(255, 255, 255, 0.92);
    backdrop-filter: blur(6px);
    border-top: 1px solid #e5e8ec;
}

.dirty-note {
    flex: 1 1 auto;
    font-size: 0.78rem;
    color: #2db400;
    font-weight: 600;
}

.dirty-note.clean {
    color: #9aa3ad;
    font-weight: 500;
}

.btn-reset,
.btn-save {
    height: 40px;
    padding: 0 18px;
    border-radius: 10px;
    font-size: 0.88rem;
    font-weight: 700;
    cursor: pointer;
}

.btn-reset {
    border: 1px solid #d6dbe1;
    background: #fff;
    color: #6b7280;
}

.btn-save {
    border: 0;
    background: #2db400;
    color: #fff;
}

.btn-save:disabled,
.btn-reset:disabled {
    opacity: 0.45;
    cursor: not-allowed;
}

/* ── 모바일 ── */
@media (max-width: 520px) {
    .pv-inputs { grid-template-columns: 1fr; }

    .slider-ctrl {
        flex-direction: column;
        align-items: stretch;
        gap: 8px;
    }

    .sl-num { justify-content: flex-end; }
}
</style>
