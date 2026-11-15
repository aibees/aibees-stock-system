<template>
    <div id="batch-setting">
        <BrandHeader :title="title" back="/menu" />

        <div class="contents">

            <!-- ── 요약 + 상단 버튼 ── -->
            <section class="toolbar">
                <p class="summary">사용 중 <b>{{ groups[0].rows.length }}</b> · 중지 {{ groups[1].rows.length }}</p>
                <div class="head-actions">
                    <button type="button" class="btn-ghost" @click="reloadScheduler" :disabled="isReloading">
                        <svg :class="{ spinning: isReloading }" xmlns="http://www.w3.org/2000/svg" width="14"
                            height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"
                            stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                            <polyline points="23 4 23 10 17 10" />
                            <polyline points="1 20 1 14 7 14" />
                            <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
                        </svg>
                        {{ isReloading ? '갱신 중…' : '스케줄러 새로고침' }}
                    </button>
                    <button type="button" class="btn-primary" @click="openAdd">+ 배치 추가</button>
                </div>
            </section>

            <div v-if="isLoading" class="loader-rows">
                <div v-for="n in 5" :key="n" class="skeleton-row"></div>
            </div>

            <template v-else>
                <!-- 사용 중 / 중지 그룹, 각 그룹은 실행 시각 순. 카드 없이 구분선 목록 -->
                <section v-for="g in groups" v-show="g.rows.length" :key="g.key" class="job-group">
                    <h2 class="group-title">{{ g.label }} <span class="count">{{ g.rows.length }}</span></h2>
                    <ul class="job-list">
                        <li v-for="row in g.rows" :key="row.job_id" class="job" :class="{ off: row.enabled_flag === 'N' }">
                            <div class="job-top">
                                <div class="job-title">
                                    <span class="job-name">{{ row.job_name }}</span>
                                    <span class="job-when">{{ cronLabel(row) }}</span>
                                </div>
                                <button type="button" :class="['toggle-btn', row.enabled_flag === 'Y' ? 'active' : 'inactive']"
                                    role="switch" :aria-checked="row.enabled_flag === 'Y' ? 'true' : 'false'"
                                    :aria-label="`${row.job_name} 사용`"
                                    @click="toggleEnabled(row)" :disabled="togglingId === row.job_id">
                                    <span class="toggle-knob"></span>
                                </button>
                            </div>

                            <!-- 최근 실행: 상태는 점 + 글자로(색만으로 구분하지 않는다) -->
                            <div class="job-last" :class="lastRun(row).cls">
                                <i class="dot" aria-hidden="true"></i>
                                <span class="lr-state">{{ lastRun(row).label }}</span>
                                <span v-if="lastRun(row).meta" class="lr-meta">{{ lastRun(row).meta }}</span>
                            </div>
                            <p v-if="row.last_run && row.last_run.desc" class="job-desc">{{ row.last_run.desc }}</p>

                            <div class="job-foot">
                                <span class="job-tech">{{ row.job_id }} · {{ row.cron_minute }} {{ row.cron_hour }} {{ row.cron_day_of_week }}</span>
                                <div class="job-actions">
                                    <button type="button" class="act" @click="openRun(row)">실행</button>
                                    <button type="button" class="act" @click="openEdit(row)">수정</button>
                                    <button type="button" class="act danger" @click="removeBatch(row)">삭제</button>
                                </div>
                            </div>
                        </li>
                    </ul>
                </section>
                <p v-if="!batchList.length" class="empty">등록된 배치가 없습니다.</p>
            </template>
        </div>

        <!-- ── 추가/수정 팝업 ── -->
        <Teleport to="body">
            <Transition name="fade">
                <div v-if="popup.visible" class="popup-overlay" @click.self="closePopup">
                    <div class="popup-panel" v-draggable>

                        <div class="popup-header">
                            <h3>{{ popup.isEdit ? '배치 수정' : '배치 추가' }}</h3>
                            <button class="btn-close" @click="closePopup">
                                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24"
                                    fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"
                                    stroke-linejoin="round">
                                    <line x1="18" y1="6" x2="6" y2="18" />
                                    <line x1="6" y1="6" x2="18" y2="18" />
                                </svg>
                            </button>
                        </div>

                        <div class="popup-body">
                            <div class="form-grid">

                                <!-- JOB ID -->
                                <div class="form-field full">
                                    <label>JOB ID <span class="req">*</span></label>
                                    <input v-model="form.job_id" :disabled="popup.isEdit"
                                        placeholder="예) STOCK_BUY_CHECK_JOB" maxlength="64" />
                                </div>

                                <!-- 배치명 -->
                                <div class="form-field full">
                                    <label>배치명 <span class="req">*</span></label>
                                    <input v-model="form.job_name" placeholder="예) 매수타겟 조회" maxlength="255" />
                                </div>

                                <!-- 모듈 -->
                                <div class="form-field full">
                                    <label>모듈 (module_name) <span class="req">*</span></label>
                                    <input v-model="form.module_name" placeholder="예) app.batches.jobs.StockBuyCheckJob"
                                        maxlength="255" />
                                </div>

                                <!-- 클래스 -->
                                <div class="form-field full">
                                    <label>클래스 (class_name) <span class="req">*</span></label>
                                    <input v-model="form.class_name" placeholder="예) StockBuyCheckJob" maxlength="45" />
                                </div>

                                <!-- CRON 분 -->
                                <div class="form-field">
                                    <label>CRON 분 <span class="req">*</span></label>
                                    <input v-model="form.cron_minute" placeholder="예) 0 또는 */30" maxlength="45" />
                                </div>

                                <!-- CRON 시 -->
                                <div class="form-field">
                                    <label>CRON 시 <span class="req">*</span></label>
                                    <input v-model="form.cron_hour" placeholder="예) 9 또는 *" maxlength="45" />
                                </div>

                                <!-- CRON 요일 -->
                                <div class="form-field full">
                                    <label>CRON 요일 <span class="req">*</span></label>
                                    <input v-model="form.cron_day_of_week" placeholder="예) mon-fri 또는 *" maxlength="45" />
                                </div>

                                <!-- 입력한 CRON 이 실제로 언제 도는지 바로 보여준다 -->
                                <p v-if="form.cron_minute && form.cron_hour" class="cron-preview full">
                                    실행 주기 <b>{{ cronLabel(form) }}</b>
                                </p>

                                <!-- 사용 여부 -->
                                <div class="form-field full">
                                    <label>사용 여부 <span class="req">*</span></label>
                                    <div class="radio-group">
                                        <label class="radio-label">
                                            <input type="radio" v-model="form.enabled_flag" value="Y" /> 사용
                                        </label>
                                        <label class="radio-label">
                                            <input type="radio" v-model="form.enabled_flag" value="N" /> 미사용
                                        </label>
                                    </div>
                                </div>

                            </div>
                        </div>

                        <div class="popup-footer">
                            <button class="btn-cancel" @click="closePopup">취소</button>
                            <button class="btn-save" @click="saveBatch" :disabled="isSaving">
                                {{ isSaving ? '저장 중…' : (popup.isEdit ? '수정 완료' : '추가') }}
                            </button>
                        </div>

                    </div>
                </div>
            </Transition>
        </Teleport>

        <!-- ── 단독실행 팝업 (raw json) ── -->
        <Teleport to="body">
            <Transition name="fade">
                <div v-if="runPopup.visible" class="popup-overlay" @click.self="closeRun">
                    <div class="popup-panel run-panel" v-draggable>

                        <div class="popup-header">
                            <h3>배치 단독실행 - {{ runPopup.job_id }}</h3>
                            <button class="btn-close" @click="closeRun">
                                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24"
                                    fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"
                                    stroke-linejoin="round">
                                    <line x1="18" y1="6" x2="6" y2="18" />
                                    <line x1="6" y1="6" x2="18" y2="18" />
                                </svg>
                            </button>
                        </div>

                        <div class="popup-body">
                            <div class="form-field full">
                                <label>요청 Body (Raw JSON)</label>
                                <textarea v-model="runPopup.rawJson" class="json-area" rows="10"
                                    placeholder='예) { "ymd": "20260614", "force": true }'></textarea>
                                <p class="hint-text" v-if="runError">{{ runError }}</p>
                            </div>
                        </div>

                        <div class="popup-footer">
                            <button class="btn-cancel" @click="closeRun">취소</button>
                            <button class="btn-save" @click="executeBatch" :disabled="isRunning">
                                {{ isRunning ? '실행 중…' : '실행' }}
                            </button>
                        </div>

                    </div>
                </div>
            </Transition>
        </Teleport>

    </div>
</template>

<script setup>
import aibeesApi, { batchApi } from '@scripts/aibeesApi.js';

const title = ref('배치 관리');

/* ── 목록 ── */
const batchList = ref([]);
const isLoading = ref(true);
const togglingId = ref(null);

const fetchBatchList = async () => {
    isLoading.value = true;
    try {
        const { data } = await aibeesApi.get('/api/v1/master/batch-jobs');
        batchList.value = data.data ?? [];
    } finally {
        isLoading.value = false;
    }
};

onMounted(async () => {
    await fetchBatchList();
});

// ── 실행 주기: CRON(분/시/요일) → 사람이 읽는 말 ──
// 실제 등록된 패턴(0 20 mon-fri, */30 9-16 mon-fri, 0 2 sat, */30 * * …)을 다룬다. 모르는 형식은 원문을 그대로 보여준다.
const DOW = { mon: '월', tue: '화', wed: '수', thu: '목', fri: '금', sat: '토', sun: '일' };
const pad2 = (v) => String(v).padStart(2, '0');
const isNum = (v) => /^\d+$/.test(v);

const dowLabel = (raw) => {
    const d = String(raw ?? '*').trim().toLowerCase();
    if (d === '*' || d === '') return '매일';
    if (d === 'mon-fri') return '평일';
    if (['sat,sun', 'sun,sat', 'sat-sun'].includes(d)) return '주말';
    if (DOW[d]) return `${DOW[d]}요일`;
    const range = d.match(/^([a-z]{3})-([a-z]{3})$/);
    if (range && DOW[range[1]] && DOW[range[2]]) return `${DOW[range[1]]}~${DOW[range[2]]}`;
    if (d.split(',').every(x => DOW[x])) return d.split(',').map(x => DOW[x]).join('·');
    return d;
};

const timeLabel = (rawM, rawH) => {
    const m = String(rawM ?? '').trim();
    const h = String(rawH ?? '').trim();
    const every = m.match(/^\*\/(\d+)$/);
    const hRange = h.match(/^(\d+)-(\d+)$/);
    if (isNum(m) && isNum(h)) return `${pad2(h)}:${pad2(m)}`;
    if (isNum(m) && /^\d+(,\d+)+$/.test(h)) return h.split(',').map(x => `${pad2(x)}:${pad2(m)}`).join(', ');
    if (every && h === '*') return `${every[1]}분마다`;
    if (every && hRange) return `${+hRange[1]}~${+hRange[2]}시 ${every[1]}분마다`;
    if (isNum(m) && h === '*') return `매시 ${pad2(m)}분`;
    if (isNum(m) && hRange) return `${+hRange[1]}~${+hRange[2]}시 매시 ${pad2(m)}분`;
    return `${m} ${h}`;
};

const cronLabel = (row) => `${dowLabel(row.cron_day_of_week)} ${timeLabel(row.cron_minute, row.cron_hour)}`;

// 정렬 키: 하루 중 첫 실행 시각(분). 매시/분 단위 반복은 0시 취급으로 맨 앞.
const firstRunMinute = (row) => {
    const h = String(row.cron_hour ?? '');
    const m = String(row.cron_minute ?? '');
    const hh = isNum(h) ? +h : (h.match(/^(\d+)/) ? +h.match(/^(\d+)/)[1] : 0);
    const mm = isNum(m) ? +m : 0;
    return hh * 60 + mm;
};

const groups = computed(() => {
    const sorted = [...batchList.value].sort((a, b) => firstRunMinute(a) - firstRunMinute(b));
    return [
        { key: 'on',  label: '사용 중', rows: sorted.filter(r => r.enabled_flag === 'Y') },
        { key: 'off', label: '중지',    rows: sorted.filter(r => r.enabled_flag !== 'Y') },
    ];
});

/* ── 최근 실행 결과(last_run: API 가 stock_batch_log 최신 1건을 붙여준다) ── */
const parseTime = (v) => (v ? new Date(String(v).replace(' ', 'T')) : null);   // 서버 값은 KST tz 없는 문자열

const whenLabel = (d) => {
    const now = new Date();
    const sameDay = (a, b) => a.toDateString() === b.toDateString();
    const yest = new Date(now); yest.setDate(now.getDate() - 1);
    const hm = `${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
    if (sameDay(d, now)) return `오늘 ${hm}`;
    if (sameDay(d, yest)) return `어제 ${hm}`;
    return `${pad2(d.getMonth() + 1)}/${pad2(d.getDate())} ${hm}`;
};

const durationLabel = (start, end) => {
    if (!start || !end) return '';
    const sec = Math.max(0, Math.round((end - start) / 1000));
    if (sec < 60) return `${sec}초`;
    if (sec < 3600) return `${Math.floor(sec / 60)}분${sec % 60 ? ` ${sec % 60}초` : ''}`;
    return `${Math.floor(sec / 3600)}시간 ${Math.floor((sec % 3600) / 60)}분`;
};

const lastRun = (row) => {
    const lr = row.last_run;
    if (!lr) return { cls: 'none', label: '실행 기록 없음', meta: '' };
    const st = String(lr.status ?? '').toUpperCase();
    const start = parseTime(lr.start_time);
    const end = parseTime(lr.end_time);
    const running = !end || ['RUNNING', 'START', 'STARTED'].includes(st);
    const [cls, label] = running ? ['run', '실행 중']
        : st === 'SUCCESS' ? ['ok', '성공']
        : ['FAIL', 'FAILED', 'ERROR'].includes(st) ? ['fail', '실패']
        : ['none', lr.status || '알 수 없음'];
    const meta = [start ? whenLabel(start) : '', running ? '' : durationLabel(start, end)].filter(Boolean).join(' · ');
    return { cls, label, meta };
};

/* ── 스케줄러 새로고침 (배치 서버의 job 재등록) ── */
const isReloading = ref(false);

const reloadScheduler = async () => {
    if (isReloading.value) return;
    if (!confirm('배치 스케줄러를 새로고침하시겠습니까?\n(DB 설정 기준으로 등록된 Job이 다시 로드됩니다)')) return;

    isReloading.value = true;
    try {
        const { data } = await batchApi.get('/api/v1/jobs/reload');
        const jobs = data?.data ?? [];
        alert(`스케줄러가 갱신되었습니다. (등록된 Job ${jobs.length}건)`);
        await fetchBatchList();
    } catch (e) {
        alert(e?.response?.data?.message ?? '스케줄러 새로고침 중 오류가 발생했습니다.');
    } finally {
        isReloading.value = false;
    }
};

/* ── 사용/미사용 토글 (PATCH) ── */
const toggleEnabled = async (row) => {
    togglingId.value = row.job_id;
    const next = row.enabled_flag === 'Y' ? 'N' : 'Y';
    try {
        await aibeesApi.patch(`/api/v1/master/batch-jobs/${row.job_id}`, { enabled_flag: next });
        row.enabled_flag = next;
    } finally {
        togglingId.value = null;
    }
};

/* ── 추가/수정 팝업 ── */
const defaultForm = () => ({
    job_id: '',
    job_name: '',
    module_name: '',
    class_name: '',
    cron_minute: '',
    cron_hour: '',
    cron_day_of_week: '',
    enabled_flag: 'Y',
});

const popup = reactive({ visible: false, isEdit: false });
const form = reactive(defaultForm());
const isSaving = ref(false);

const openAdd = () => {
    Object.assign(form, defaultForm());
    popup.isEdit = false;
    popup.visible = true;
};

const openEdit = (row) => {
    Object.assign(form, { ...row });
    popup.isEdit = true;
    popup.visible = true;
};

const closePopup = () => { popup.visible = false; };

const saveBatch = async () => {
    if (!form.job_id || !form.job_name || !form.module_name || !form.class_name
        || !form.cron_minute || !form.cron_hour || !form.cron_day_of_week) {
        alert('필수 항목을 모두 입력해 주세요.');
        return;
    }
    isSaving.value = true;
    try {
        if (popup.isEdit) {
            await aibeesApi.put(`/api/v1/master/batch-jobs/${form.job_id}`, { ...form });
        } else {
            await aibeesApi.post('/api/v1/master/batch-jobs', { ...form });
        }
        closePopup();
        await fetchBatchList();
    } finally {
        isSaving.value = false;
    }
};

/* ── 삭제 ── */
const removeBatch = async (row) => {
    if (!confirm(`'${row.job_name}' 배치를 삭제하시겠습니까?`)) return;
    await aibeesApi.delete(`/api/v1/master/batch-jobs/${row.job_id}`);
    await fetchBatchList();
};

/* ── 단독실행 팝업 ── */
const runPopup = reactive({ visible: false, job_id: '', rawJson: '{\n\n}' });
const isRunning = ref(false);
const runError = ref('');

const openRun = (row) => {
    runPopup.job_id = row.job_id;
    runPopup.rawJson = '{\n\n}';
    runError.value = '';
    runPopup.visible = true;
};

const closeRun = () => { runPopup.visible = false; };

const executeBatch = async () => {
    let body = {};
    try {
        body = runPopup.rawJson.trim() === '' ? {} : JSON.parse(runPopup.rawJson);
    } catch (e) {
        runError.value = 'JSON 형식이 올바르지 않습니다.';
        return;
    }
    console.log("body")
    console.log(body)
    isRunning.value = true;
    runError.value = '';
    try {
        console.log("runPopup jobId : " + runPopup.job_id);
        await batchApi.post(`/api/v1/jobs/once/${runPopup.job_id}`, body);
        alert('배치 실행 요청이 전송되었습니다.');
        closeRun();
    } catch (e) {
        runError.value = '실행 요청 중 오류가 발생했습니다.';
    } finally {
        isRunning.value = false;
    }
};
</script>

<style scoped lang="scss">
// 양봉상회 토큰(홈·매수추천과 동일). 기존 변수명은 팝업 스타일이 쓰고 있어 값만 브랜드 톤으로 바꿔 둔다.
$white:    #ffffff;
$line:     #EFE2BC;
$line-2:   #EAD9A6;
$chip:     #F6EBC8;
$hero:     #74462A;
$brown:    #7A4423;
$ink:      #2B1D14;
$sub:      #6B5B4E;
$sub-2:    #7A6B5D;
$cream:    #FFF8E1;
$ok:       #2E9E5B;
$fail:     #C8282A;
$run:      #E07A00;

$gray-50:  #FFFDF5;
$gray-100: #F3EAD2;
$gray-200: $line-2;
$gray-300: $line-2;
$gray-400: #9A8C7E;
$gray-500: $sub;
$gray-700: #4A3628;
$gray-900: $ink;
$blue:     $brown;
$navy:     $hero;
$red:      $fail;

#batch-setting {
    min-height: 100vh;
    background: $white;
    color: $ink;
    text-align: left;
    font-family: 'Pretendard', 'IBM Plex Sans KR', -apple-system, 'Apple SD Gothic Neo', sans-serif;
    font-variant-numeric: tabular-nums;
}

.contents {
    max-width: 760px;
    margin: 0 auto;
    padding: 16px 16px calc(96px + env(safe-area-inset-bottom, 0px));
}

/* ── 요약 + 상단 버튼 ── */
.toolbar {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    margin-bottom: 8px;

    .summary { margin: 0; font-size: 14px; color: $sub; b { color: $ink; font-size: 16px; } }
}
.head-actions { display: flex; gap: 8px; }

.btn-ghost,
.btn-primary {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    min-height: 40px;
    padding: 0 14px;
    border-radius: 10px;
    font-size: 14px;
    font-weight: 600;
    font-family: inherit;
    cursor: pointer;
    white-space: nowrap;
}
.btn-ghost {
    border: 1px solid $line-2;
    background: $white;
    color: $brown;
    &:disabled { color: $sub-2; cursor: default; }
}
.btn-primary { border: 0; background: $hero; color: $cream; }
.btn-ghost:focus-visible,
.btn-primary:focus-visible { outline: 2px solid $brown; outline-offset: 2px; }

.spinning { animation: spin 0.9s linear infinite; }
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

/* ── 그룹 ── */
.job-group { margin-top: 18px; }
.group-title {
    margin: 0 0 4px;
    font-size: 17px;
    font-weight: 700;
    color: $ink;
    .count { color: #A0662F; margin-left: 2px; }
}

/* ── 배치 목록: 카드 없이 구분선 ── */
.job-list {
    margin: 0;
    padding: 0;
    list-style: none;
    border-top: 1px solid $line;
}

.job {
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding: 14px 0;
    border-bottom: 1px solid $line;

    &.off .job-title,
    &.off .job-last,
    &.off .job-desc { opacity: .55; }
}

.job-top {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
}
.job-title { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.job-name { font-size: 16px; font-weight: 700; color: $ink; word-break: keep-all; }
.job-when { font-size: 14px; font-weight: 600; color: $brown; }

// 최근 실행: 점 + 글자
.job-last {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 2px 8px;
    font-size: 13px;

    .dot { width: 8px; height: 8px; border-radius: 4px; background: $sub-2; flex-shrink: 0; }
    .lr-state { font-weight: 700; color: $sub; }
    .lr-meta { color: $sub; }

    &.ok   { .dot { background: $ok; }   .lr-state { color: #23784A; } }
    &.fail { .dot { background: $fail; } .lr-state { color: $fail; } }
    &.run  { .dot { background: $run; }  .lr-state { color: #B05F00; } }
    &.none { .lr-state { font-weight: 500; color: $sub-2; } }
}
.job-desc {
    margin: 0;
    font-size: 13px;
    line-height: 1.5;
    color: $sub;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
    word-break: keep-all;
    overflow-wrap: anywhere;
}

// 기술 정보(JOB ID · 원본 CRON)는 한 줄로 줄이고 버튼은 같은 줄 오른쪽에 둔다
.job-foot {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: 2px;
}
.job-tech {
    flex: 1 1 auto;
    min-width: 0;
    font-family: ui-monospace, 'SFMono-Regular', Menlo, monospace;
    font-size: 11.5px;
    color: $sub-2;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.job-actions { display: flex; gap: 0; flex-shrink: 0; }
.act {
    min-height: 32px;
    padding: 0 8px;
    border: 0;
    border-radius: 8px;
    background: transparent;
    color: $brown;
    font-size: 13px;
    font-weight: 600;
    font-family: inherit;
    cursor: pointer;

    &:hover { background: rgba(239, 226, 188, .4); }
    &:focus-visible { outline: 2px solid $brown; outline-offset: 0; }
    &.danger { color: $fail; }
}

/* ── 사용 스위치 ── */
.toggle-btn {
    position: relative;
    flex-shrink: 0;
    width: 44px;
    height: 26px;
    border: 0;
    border-radius: 13px;
    cursor: pointer;
    transition: background .15s;

    &.active   { background: $hero; }
    &.inactive { background: $line-2; }
    &:disabled { opacity: .6; cursor: default; }
    &:focus-visible { outline: 2px solid $brown; outline-offset: 2px; }

    .toggle-knob {
        position: absolute;
        top: 3px;
        left: 3px;
        width: 20px;
        height: 20px;
        border-radius: 10px;
        background: $white;
        box-shadow: 0 1px 2px rgba(74, 40, 20, .25);
        transition: transform .15s;
    }
    &.active .toggle-knob { transform: translateX(18px); }
}

/* ── 로딩 / 빈 상태 ── */
.loader-rows { display: flex; flex-direction: column; margin-top: 18px; border-top: 1px solid $line; }
.skeleton-row {
    height: 96px;
    border-bottom: 1px solid $line;
    background: rgba(239, 226, 188, .3);
    animation: pulse 1.6s infinite ease-in-out;
}
.empty { padding: 48px 0; text-align: center; color: $sub; font-size: 14px; }

/* ── Popup ── */
.popup-overlay {
    position: fixed;
    inset: 0;
    background: rgba(43, 29, 20, .45);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 2000;
    padding: 16px;

    // 모바일: 화면 아래에서 올라오는 시트(전체 폭, 위만 둥글게, 하단 세이프 에어리어 포함)
    @media (max-width: 600px) {
        align-items: flex-end;
        padding: 0;
    }
}

.popup-panel {
    background: $white;
    border-radius: 16px;
    width: 100%;
    max-width: 560px;
    max-height: 90vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    box-shadow: 0 12px 40px rgba(74, 40, 20, .2);

    @media (max-width: 600px) {
        max-width: none;
        max-height: 88vh;
        border-radius: 16px 16px 0 0;
        padding-bottom: env(safe-area-inset-bottom, 0px);
    }
}

.run-panel {
    max-width: 520px;
}

.popup-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 18px 20px 14px;
    border-bottom: 1px solid $gray-100;

    h3 {
        margin: 0;
        font-size: 1rem;
        font-weight: 700;
        color: $gray-900;
        word-break: break-all;
    }

    .btn-close {
        border: none;
        background: none;
        cursor: pointer;
        color: $gray-400;
        padding: 4px;
        border-radius: 0;
        display: flex;
        align-items: center;
        flex-shrink: 0;
        transition: color .12s;

        &:hover {
            color: $gray-900;
        }
    }
}

.popup-body {
    padding: 16px 20px 20px;
    overflow-y: auto;
    overflow-x: hidden;   // 입력칸이 넘쳐도 가로로 밀리지 않게
    flex: 1;
}

.form-grid {
    display: grid;
    // minmax(0, …) 이 핵심 — 1fr 은 입력칸의 최소 폭 아래로 못 줄어 좁은 화면에서 팝업 밖으로 넘친다
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
    gap: 14px 12px;

    .cron-preview {
        grid-column: 1 / -1;
        margin: -4px 0 0;
        font-size: 13px;
        color: $sub;
        b { color: $brown; margin-left: 4px; }
    }

    .form-field {
        display: flex;
        flex-direction: column;
        gap: 5px;

        &.full {
            grid-column: 1 / -1;
        }

        label {
            font-size: 0.78rem;
            font-weight: 600;
            color: $gray-700;
        }

        .req {
            color: $red;
            margin-left: 2px;
        }

        input[type="text"],
        input[type="number"],
        input:not([type="radio"]) {
            width: 100%;
            min-width: 0;
            box-sizing: border-box;
            min-height: 42px;
            padding: 0 12px;
            border: 1px solid $gray-200;
            border-radius: 10px;
            font-size: 16px;
            color: $gray-900;
            font-family: inherit;
            background: $white;
            outline: none;
            transition: border-color .15s;

            &:focus {
                border-color: $blue;
            }

            &:disabled {
                background: $gray-50;
                color: $gray-400;
            }

            &::placeholder {
                color: $gray-400;
            }
        }

        .radio-group {
            display: flex;
            gap: 16px;
            padding: 8px 0 4px;
        }

        .radio-label {
            display: flex;
            align-items: center;
            gap: 5px;
            font-size: 0.84rem;
            font-weight: 500;
            color: $gray-700;
            cursor: pointer;

            input[type="radio"] {
                cursor: pointer;
                accent-color: $navy;
            }
        }
    }
}

/* raw json textarea */
.form-field.full {
    .json-area {
        width: 100%;
        box-sizing: border-box;
        padding: 10px;
        border: 1px solid $gray-200;
        border-radius: 10px;
        font-size: 14px;
        font-family: 'SFMono-Regular', Consolas, monospace;
        color: $gray-900;
        background: $gray-50;
        outline: none;
        resize: vertical;
        transition: border-color .15s;

        &:focus {
            border-color: $blue;
        }
    }

    .hint-text {
        margin: 4px 0 0;
        font-size: 0.76rem;
        color: $red;
    }
}

.popup-footer {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    padding: 14px 20px 18px;
    border-top: 1px solid $gray-100;

    .btn-cancel {
        min-height: 42px;
        padding: 0 18px;
        border: 1px solid $gray-200;
        border-radius: 10px;
        background: $white;
        color: $gray-700;
        font-size: 0.84rem;
        font-weight: 600;
        cursor: pointer;
        font-family: inherit;
        transition: border-color .12s;

        &:hover {
            border-color: $gray-400;
        }
    }

    .btn-save {
        min-height: 42px;
        padding: 0 20px;
        border: none;
        border-radius: 10px;
        background: $navy;
        color: $cream;
        font-size: 0.84rem;
        font-weight: 700;
        cursor: pointer;
        font-family: inherit;
        transition: background .15s;

        &:hover {
            background: $brown;
        }

        &:disabled {
            opacity: .55;
            cursor: not-allowed;
        }
    }
}

/* ── Transition ── */
.fade-enter-active,
.fade-leave-active {
    transition: opacity .18s;
}

.fade-enter-from,
.fade-leave-to {
    opacity: 0;
}

@keyframes pulse {

    0%,
    100% {
        opacity: .5;
    }

    50% {
        opacity: .9;
    }
}
</style>
