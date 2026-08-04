<template>
    <div id="batch-setting">
        <Headers :prop_title="title" />

        <div class="contents">

            <!-- ── 상단 타이틀 + 추가 버튼 ── -->
            <section class="head-desc">
                <div class="head-left">
                    <h2>배치 작업 설정</h2>
                    <p class="sub-text">등록된 배치 작업을 관리하고 단독 실행할 수 있습니다</p>
                </div>
                <button class="btn-add" @click="openAdd">
                    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none"
                        stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                        <line x1="12" y1="5" x2="12" y2="19" />
                        <line x1="5" y1="12" x2="19" y2="12" />
                    </svg>
                    배치 추가
                </button>
            </section>

            <!-- ── 데스크탑 테이블 ── -->
            <section class="table-section">
                <div v-if="isLoading" class="loader-rows">
                    <div v-for="n in 6" :key="n" class="skeleton-row"></div>
                </div>

                <table v-else class="batch-table">
                    <thead>
                        <tr>
                            <th class="col-id">JOB ID</th>
                            <th class="col-name">배치명</th>
                            <th class="col-module">모듈</th>
                            <th class="col-class">클래스</th>
                            <th class="col-cron">CRON (분/시/요일)</th>
                            <th class="col-flag">사용</th>
                            <th class="col-action"></th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr v-for="row in batchList" :key="row.job_id"
                            :class="{ 'row-disabled': row.enabled_flag === 'N' }">
                            <td class="col-id"><span class="code-chip">{{ row.job_id }}</span></td>
                            <td class="col-name">{{ row.job_name }}</td>
                            <td class="col-module"><span class="path-text">{{ row.module_name }}</span></td>
                            <td class="col-class"><span class="comp-text">{{ row.class_name }}</span></td>
                            <td class="col-cron">
                                <span class="cron-chip">{{ row.cron_minute }} {{ row.cron_hour }} {{
                                    row.cron_day_of_week }}</span>
                            </td>
                            <td class="col-flag">
                                <button :class="['toggle-btn', row.enabled_flag === 'Y' ? 'active' : 'inactive']"
                                    @click="toggleEnabled(row)" :disabled="togglingId === row.job_id">
                                    <span class="toggle-knob"></span>
                                </button>
                            </td>
                            <td class="col-action">
                                <div class="action-group">
                                    <button class="btn-run" @click="openRun(row)">단독실행</button>
                                    <button class="btn-edit" @click="openEdit(row)">수정</button>
                                    <button class="btn-delete" @click="removeBatch(row)">삭제</button>
                                </div>
                            </td>
                        </tr>
                        <tr v-if="!isLoading && batchList.length === 0">
                            <td colspan="7" class="empty-cell">등록된 배치가 없습니다.</td>
                        </tr>
                    </tbody>
                </table>
            </section>

            <!-- ── 모바일 리스트 (ul/li) ── -->
            <section class="mobile-list">
                <div v-if="isLoading" class="loader-rows">
                    <div v-for="n in 4" :key="n" class="skeleton-row"></div>
                </div>

                <ul v-else class="batch-ul">
                    <li v-for="row in batchList" :key="row.job_id" class="batch-li"
                        :class="{ 'li-disabled': row.enabled_flag === 'N' }">
                        <div class="li-top">
                            <span class="code-chip">{{ row.job_id }}</span>
                            <button :class="['toggle-btn', row.enabled_flag === 'Y' ? 'active' : 'inactive']"
                                @click="toggleEnabled(row)" :disabled="togglingId === row.job_id">
                                <span class="toggle-knob"></span>
                            </button>
                        </div>
                        <div class="li-name">{{ row.job_name }}</div>
                        <div class="li-row">
                            <span class="li-label">모듈</span>
                            <span class="path-text">{{ row.module_name }}</span>
                        </div>
                        <div class="li-row">
                            <span class="li-label">클래스</span>
                            <span class="comp-text">{{ row.class_name }}</span>
                        </div>
                        <div class="li-row">
                            <span class="li-label">CRON</span>
                            <span class="cron-chip">{{ row.cron_minute }} {{ row.cron_hour }} {{
                                row.cron_day_of_week }}</span>
                        </div>
                        <div class="li-actions">
                            <button class="btn-run" @click="openRun(row)">단독실행</button>
                            <button class="btn-edit" @click="openEdit(row)">수정</button>
                            <button class="btn-delete" @click="removeBatch(row)">삭제</button>
                        </div>
                    </li>
                    <li v-if="batchList.length === 0" class="empty-cell">등록된 배치가 없습니다.</li>
                </ul>
            </section>
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

const title = ref('배치 설정');

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
$white: #ffffff;
$gray-50: #f8f9fa;
$gray-100: #ebebeb;
$gray-200: #d0d0d0;
$gray-400: #909090;
$gray-500: #6b6b6b;
$gray-700: #333333;
$gray-900: #111111;
$blue: #1971c2;
$navy: #1c3d6e;
$red: #c92a2a;
$amber: #e67700;
$green: #2f9e44;

#batch-setting {
    min-height: 100vh;
    background: $gray-50;
    color: $gray-900;
    font-family: 'Pretendard', -apple-system, sans-serif;
}

.contents {
    max-width: 1200px;
    margin: 0 auto;
    padding: 28px 16px 100px;
}

/* ── Head ── */
.head-desc {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    margin-bottom: 20px;

    h2 {
        font-size: 1.4rem;
        font-weight: 700;
        margin: 0;
        color: $gray-900;
    }

    .sub-text {
        font-size: 0.82rem;
        color: $gray-500;
        margin: 4px 0 0;
    }
}

.btn-add {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 8px 16px;
    background: $navy;
    color: $white;
    border: none;
    border-radius: 0.4rem;
    font-size: 0.84rem;
    font-weight: 600;
    cursor: pointer;
    font-family: inherit;
    transition: background .15s;

    &:hover {
        background: darken(#1c3d6e, 6%);
    }
}

/* ── Table (Desktop) ── */
.table-section {
    background: $white;
    border: 1px solid $gray-200;
    border-radius: 0.6rem;
    overflow: hidden;
    overflow-x: auto;

    @media (max-width: 860px) {
        display: none;
    }
}

.batch-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.83rem;

    thead tr {
        background: $gray-50;
        border-bottom: 1px solid $gray-200;
    }

    th {
        padding: 10px 12px;
        text-align: left;
        font-size: 0.72rem;
        font-weight: 700;
        color: $gray-500;
        letter-spacing: .04em;
        text-transform: uppercase;
        white-space: nowrap;
    }

    td {
        padding: 10px 12px;
        border-bottom: 1px solid $gray-100;
        vertical-align: middle;
        color: $gray-700;
    }

    tbody tr:last-child td {
        border-bottom: none;
    }

    tbody tr:hover td {
        background: $gray-50;
    }

    .row-disabled td {
        opacity: .45;
    }
}

/* column widths */
.col-id {
    width: 170px;
}

.col-name {
    min-width: 160px;
}

.col-module {
    min-width: 220px;
}

.col-class {
    width: 150px;
}

.col-cron {
    width: 160px;
}

.col-flag {
    width: 60px;
    text-align: center;
}

.col-action {
    width: 200px;
    text-align: right;
}

.action-group {
    display: flex;
    gap: 6px;
    justify-content: flex-end;
}

/* chips */
.code-chip {
    font-size: 0.72rem;
    font-weight: 600;
    background: $gray-100;
    color: $gray-700;
    padding: 2px 7px;
    border-radius: 0.3rem;
    border: 1px solid $gray-200;
    word-break: break-all;
}

.cron-chip {
    font-size: 0.72rem;
    background: #dbe4ff;
    color: $navy;
    padding: 2px 7px;
    border-radius: 0.3rem;
    border: 1px solid #bac8ff;
    font-family: 'SFMono-Regular', Consolas, monospace;
    white-space: nowrap;
}

.path-text,
.comp-text {
    font-family: 'SFMono-Regular', Consolas, monospace;
    font-size: 0.78rem;
    color: $gray-700;
    word-break: break-all;
}

/* toggle */
.toggle-btn {
    position: relative;
    width: 36px;
    height: 20px;
    border-radius: 10px;
    border: none;
    cursor: pointer;
    transition: background .2s;
    padding: 0;
    flex-shrink: 0;

    &.active {
        background: $green;
    }

    &.inactive {
        background: $gray-200;
    }

    &:disabled {
        opacity: .5;
        cursor: not-allowed;
    }

    .toggle-knob {
        position: absolute;
        top: 3px;
        width: 14px;
        height: 14px;
        border-radius: 50%;
        background: $white;
        transition: left .2s;
    }

    &.active .toggle-knob {
        left: 19px;
    }

    &.inactive .toggle-knob {
        left: 3px;
    }
}

.btn-edit,
.btn-run,
.btn-delete {
    padding: 4px 10px;
    font-size: 0.75rem;
    font-weight: 600;
    border: 1px solid $gray-200;
    border-radius: 0.3rem;
    background: $white;
    color: $gray-700;
    cursor: pointer;
    font-family: inherit;
    transition: border-color .12s, color .12s;
    white-space: nowrap;

    &:hover {
        border-color: $blue;
        color: $blue;
    }
}

.btn-run:hover {
    border-color: $green;
    color: $green;
}

.btn-delete:hover {
    border-color: $red;
    color: $red;
}

/* skeleton */
.loader-rows {
    padding: 8px;
}

.skeleton-row {
    height: 42px;
    background: $gray-100;
    border-radius: 0.4rem;
    margin-bottom: 6px;
    animation: pulse 1.6s infinite ease-in-out;
}

.empty-cell {
    text-align: center;
    padding: 60px 0;
    color: $gray-400;
    font-size: 0.88rem;
}

/* ── Mobile List (ul/li) ── */
.mobile-list {
    display: none;

    @media (max-width: 860px) {
        display: block;
    }
}

.batch-ul {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 10px;
}

.batch-li {
    background: $white;
    border: 1px solid $gray-200;
    border-radius: 0.6rem;
    padding: 14px;

    &.li-disabled {
        opacity: .55;
    }
}

.li-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
}

.li-name {
    font-size: 0.95rem;
    font-weight: 700;
    color: $gray-900;
    margin-bottom: 8px;
}

.li-row {
    display: flex;
    gap: 8px;
    align-items: flex-start;
    font-size: 0.8rem;
    margin-bottom: 4px;

    .li-label {
        flex-shrink: 0;
        width: 44px;
        color: $gray-500;
        font-weight: 600;
    }
}

.li-actions {
    display: flex;
    gap: 6px;
    margin-top: 10px;

    button {
        flex: 1;
        text-align: center;
    }
}

/* ── Popup ── */
.popup-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, .45);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 2000;
    padding: 16px;
}

.popup-panel {
    background: $white;
    border-radius: 0.7rem;
    width: 100%;
    max-width: 560px;
    max-height: 90vh;
    display: flex;
    flex-direction: column;
    box-shadow: 0 8px 40px rgba(0, 0, 0, .18);
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
        border-radius: 0.3rem;
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
    padding: 20px;
    overflow-y: auto;
    flex: 1;
}

.form-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 14px 16px;

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
            padding: 8px 10px;
            border: 1px solid $gray-200;
            border-radius: 0.4rem;
            font-size: 0.84rem;
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
        padding: 10px;
        border: 1px solid $gray-200;
        border-radius: 0.4rem;
        font-size: 0.82rem;
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
        padding: 8px 18px;
        border: 1px solid $gray-200;
        border-radius: 0.4rem;
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
        padding: 8px 20px;
        border: none;
        border-radius: 0.4rem;
        background: $navy;
        color: $white;
        font-size: 0.84rem;
        font-weight: 700;
        cursor: pointer;
        font-family: inherit;
        transition: background .15s;

        &:hover {
            background: darken(#1c3d6e, 6%);
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
