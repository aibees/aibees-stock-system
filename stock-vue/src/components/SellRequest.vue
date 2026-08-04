<template>
    <div id="sell-request">
        <Headers :prop_title="title" />

        <div class="contents">

            <!-- ── 상단 타이틀 + 추가 버튼 ── -->
            <section class="head-desc">
                <div class="head-left">
                    <h2>매도신호 신청</h2>
                    <p class="sub-text">매도 체크를 원하는 종목을 등록하면 배치가 매도 신호를 점검합니다 (최대 {{ MAX_COUNT }}개)</p>
                </div>
                <button class="btn-add" @click="openAdd" :disabled="isMaxReached"
                    :title="isMaxReached ? `최대 ${MAX_COUNT}개까지 등록할 수 있습니다` : ''">
                    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none"
                        stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                        <line x1="12" y1="5" x2="12" y2="19" />
                        <line x1="5" y1="12" x2="19" y2="12" />
                    </svg>
                    종목 추가 ({{ sellList.length }}/{{ MAX_COUNT }})
                </button>
            </section>

            <!-- ── 데스크탑 테이블 ── -->
            <section class="table-section">
                <div v-if="isLoading" class="loader-rows">
                    <div v-for="n in 5" :key="n" class="skeleton-row"></div>
                </div>

                <table v-else class="sell-table">
                    <thead>
                        <tr>
                            <th class="col-code">종목코드</th>
                            <th class="col-name">종목명</th>
                            <th class="col-date">매수체결일</th>
                            <th class="col-price">매수평균단가</th>
                            <th class="col-qty">보유수량</th>
                            <th class="col-memo">메모</th>
                            <th class="col-flag">사용</th>
                            <th class="col-action"></th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr v-for="row in sellList" :key="row.stock_code"
                            :class="{ 'row-disabled': row.enabled_flag === 'N' }">
                            <td class="col-code"><span class="code-chip">{{ row.stock_code }}</span></td>
                            <td class="col-name">{{ row.stock_name }}</td>
                            <td class="col-date">{{ formatDate(row.entry_date) }}</td>
                            <td class="col-price num">{{ formatNumber(row.entry_price) }}</td>
                            <td class="col-qty num">{{ formatNumber(row.hold_qty) }}</td>
                            <td class="col-memo"><span class="memo-text">{{ row.memo }}</span></td>
                            <td class="col-flag">
                                <button :class="['toggle-btn', row.enabled_flag === 'Y' ? 'active' : 'inactive']"
                                    @click="toggleEnabled(row)" :disabled="togglingId === row.stock_code">
                                    <span class="toggle-knob"></span>
                                </button>
                            </td>
                            <td class="col-action">
                                <div class="action-group">
                                    <button class="btn-edit" @click="openEdit(row)">수정</button>
                                    <button class="btn-delete" @click="removeRow(row)">삭제</button>
                                </div>
                            </td>
                        </tr>
                        <tr v-if="!isLoading && sellList.length === 0">
                            <td colspan="8" class="empty-cell">등록된 종목이 없습니다. '종목 추가'로 등록해 주세요.</td>
                        </tr>
                    </tbody>
                </table>
            </section>

            <!-- ── 모바일 리스트 (ul/li) ── -->
            <section class="mobile-list">
                <div v-if="isLoading" class="loader-rows">
                    <div v-for="n in 3" :key="n" class="skeleton-row"></div>
                </div>

                <ul v-else class="sell-ul">
                    <li v-for="row in sellList" :key="row.stock_code" class="sell-li"
                        :class="{ 'li-disabled': row.enabled_flag === 'N' }">
                        <div class="li-top">
                            <span class="code-chip">{{ row.stock_code }}</span>
                            <button :class="['toggle-btn', row.enabled_flag === 'Y' ? 'active' : 'inactive']"
                                @click="toggleEnabled(row)" :disabled="togglingId === row.stock_code">
                                <span class="toggle-knob"></span>
                            </button>
                        </div>
                        <div class="li-name">{{ row.stock_name }}</div>
                        <div class="li-row">
                            <span class="li-label">체결일</span>
                            <span>{{ formatDate(row.entry_date) }}</span>
                        </div>
                        <div class="li-row">
                            <span class="li-label">평단가</span>
                            <span>{{ formatNumber(row.entry_price) }}</span>
                        </div>
                        <div class="li-row">
                            <span class="li-label">수량</span>
                            <span>{{ formatNumber(row.hold_qty) }}</span>
                        </div>
                        <div class="li-row" v-if="row.memo">
                            <span class="li-label">메모</span>
                            <span class="memo-text">{{ row.memo }}</span>
                        </div>
                        <div class="li-actions">
                            <button class="btn-edit" @click="openEdit(row)">수정</button>
                            <button class="btn-delete" @click="removeRow(row)">삭제</button>
                        </div>
                    </li>
                    <li v-if="sellList.length === 0" class="empty-cell">등록된 종목이 없습니다.</li>
                </ul>
            </section>
        </div>

        <!-- ── 추가/수정 팝업 ── -->
        <Teleport to="body">
            <Transition name="fade">
                <div v-if="popup.visible" class="popup-overlay" @click.self="closePopup">
                    <div class="popup-panel" v-draggable>

                        <div class="popup-header">
                            <h3>{{ popup.isEdit ? '종목 수정' : '종목 추가' }}</h3>
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

                                <!-- 종목 선택 -->
                                <div class="form-field full">
                                    <label>종목 <span class="req">*</span></label>
                                    <div class="stock-picker">
                                        <input class="stock-display" :value="stockDisplay" readonly
                                            placeholder="종목을 선택하세요" />
                                        <button class="btn-pick" @click="openStockSearch" :disabled="popup.isEdit">
                                            종목 선택
                                        </button>
                                    </div>
                                </div>

                                <!-- 매수 체결일 -->
                                <div class="form-field">
                                    <label>매수 체결일 <span class="req">*</span></label>
                                    <input type="date" v-model="form.entry_date_ui" />
                                </div>

                                <!-- 매수 평균단가 -->
                                <div class="form-field">
                                    <label>매수 평균단가</label>
                                    <input type="number" v-model="form.entry_price" placeholder="예) 12500" min="0"
                                        step="any" />
                                </div>

                                <!-- 보유 수량 -->
                                <div class="form-field">
                                    <label>보유 수량 <span class="req">*</span></label>
                                    <input type="number" v-model="form.hold_qty" placeholder="예) 100" min="0"
                                        step="any" />
                                </div>

                                <!-- 사용 여부 -->
                                <div class="form-field">
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

                                <!-- 메모 -->
                                <div class="form-field full">
                                    <label>메모</label>
                                    <input v-model="form.memo" placeholder="예) 목표가 도달 시 매도" maxlength="255" />
                                </div>

                            </div>
                        </div>

                        <div class="popup-footer">
                            <button class="btn-cancel" @click="closePopup">취소</button>
                            <button class="btn-save" @click="saveRow" :disabled="isSaving">
                                {{ isSaving ? '저장 중…' : (popup.isEdit ? '수정 완료' : '추가') }}
                            </button>
                        </div>

                    </div>
                </div>
            </Transition>
        </Teleport>

        <!-- ── 종목 검색 layered popup ── -->
        <Teleport to="body">
            <Transition name="fade">
                <div v-if="stockSearch.visible" class="popup-overlay layer-top" @click.self="closeStockSearch">
                    <div class="popup-panel search-panel" v-draggable>

                        <div class="popup-header">
                            <h3>종목 검색</h3>
                            <button class="btn-close" @click="closeStockSearch">
                                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24"
                                    fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"
                                    stroke-linejoin="round">
                                    <line x1="18" y1="6" x2="6" y2="18" />
                                    <line x1="6" y1="6" x2="18" y2="18" />
                                </svg>
                            </button>
                        </div>

                        <div class="popup-body">
                            <!-- 검색 바 -->
                            <div class="search-bar">
                                <input v-model="stockSearch.keyword" @keyup.enter="runStockSearch"
                                    placeholder="종목코드 또는 종목명 입력" autocomplete="off" ref="searchInputRef" />
                                <button class="btn-search" @click="runStockSearch" :disabled="stockSearch.loading">
                                    {{ stockSearch.loading ? '검색 중…' : '검색' }}
                                </button>
                            </div>

                            <!-- 결과 리스트 -->
                            <div class="search-result">
                                <ul class="result-header">
                                    <li>
                                        <div class="item s_code">코드</div>
                                        <div class="item s_name">종목명</div>
                                        <div class="item s_type">구분</div>
                                    </li>
                                </ul>
                                <ul class="result-list">
                                    <li v-for="(data, idx) in stockSearch.list" :key="idx" class="result-item"
                                        @click="pickStock(data)">
                                        <div class="item s_code">{{ data.stock_code }}</div>
                                        <div class="item s_name">{{ data.stock_name }}</div>
                                        <div class="item s_type">{{ data.type }}</div>
                                    </li>
                                    <li v-if="stockSearch.searched && stockSearch.list.length === 0"
                                        class="result-empty">
                                        검색 결과가 없습니다.
                                    </li>
                                    <li v-if="!stockSearch.searched" class="result-empty">
                                        종목코드나 종목명을 입력한 뒤 검색하세요.
                                    </li>
                                </ul>
                            </div>
                        </div>

                    </div>
                </div>
            </Transition>
        </Teleport>

    </div>
</template>

<script setup>
import aibeesApi from '@scripts/aibeesApi.js';

const title = ref('매도신호 신청');
const MAX_COUNT = 5;

/* ── 목록 ── */
const sellList = ref([]);
const isLoading = ref(true);
const togglingId = ref(null);

const isMaxReached = computed(() => sellList.value.length >= MAX_COUNT);

const fetchSellList = async () => {
    isLoading.value = true;
    try {
        // 백엔드는 JWT 토큰의 user_id 기준으로 본인 데이터만 반환한다.
        const { data } = await aibeesApi.get('/api/v1/sell-requests');
        sellList.value = data.data ?? [];
    } finally {
        isLoading.value = false;
    }
};

onMounted(async () => {
    await fetchSellList();
});

/* ── 사용/미사용 토글 (PATCH) ── */
const toggleEnabled = async (row) => {
    togglingId.value = row.stock_code;
    const next = row.enabled_flag === 'Y' ? 'N' : 'Y';
    try {
        await aibeesApi.patch(`/api/v1/sell-requests/${row.stock_code}`, { enabled_flag: next });
        row.enabled_flag = next;
    } finally {
        togglingId.value = null;
    }
};

/* ── 추가/수정 팝업 ── */
const defaultForm = () => ({
    stock_code: '',
    stock_name: '',
    entry_date_ui: '',   // <input type="date"> 용 YYYY-MM-DD
    entry_price: '',
    hold_qty: '',
    memo: '',
    enabled_flag: 'Y',
});

const popup = reactive({ visible: false, isEdit: false });
const form = reactive(defaultForm());
const isSaving = ref(false);

const stockDisplay = computed(() =>
    form.stock_code ? `${form.stock_name} (${form.stock_code})` : ''
);

// YYYYMMDD <-> YYYY-MM-DD 변환
const toUiDate = (ymd) => (ymd && ymd.length === 8)
    ? `${ymd.slice(0, 4)}-${ymd.slice(4, 6)}-${ymd.slice(6, 8)}` : '';
const toYmd = (ui) => ui ? ui.replaceAll('-', '') : null;

const openAdd = () => {
    if (isMaxReached.value) {
        alert(`최대 ${MAX_COUNT}개까지만 등록할 수 있습니다.`);
        return;
    }
    Object.assign(form, defaultForm());
    popup.isEdit = false;
    popup.visible = true;
};

const openEdit = (row) => {
    Object.assign(form, {
        stock_code: row.stock_code,
        stock_name: row.stock_name,
        entry_date_ui: toUiDate(row.entry_date),
        entry_price: row.entry_price ?? '',
        hold_qty: row.hold_qty ?? '',
        memo: row.memo ?? '',
        enabled_flag: row.enabled_flag ?? 'Y',
    });
    popup.isEdit = true;
    popup.visible = true;
};

const closePopup = () => { popup.visible = false; };

const saveRow = async () => {
    if (!form.stock_code) {
        alert('종목을 선택해 주세요.');
        return;
    }
    if (!form.entry_date_ui) {
        alert('매수 체결일을 입력해 주세요.');
        return;
    }
    if (form.hold_qty === '' || form.hold_qty === null || form.hold_qty === undefined) {
        alert('보유 수량을 입력해 주세요.');
        return;
    }
    // 신규 등록 시 최대 개수 / 중복 방어
    if (!popup.isEdit) {
        if (isMaxReached.value) {
            alert(`최대 ${MAX_COUNT}개까지만 등록할 수 있습니다.`);
            return;
        }
        if (sellList.value.some(r => r.stock_code === form.stock_code)) {
            alert('이미 등록된 종목입니다.');
            return;
        }
    }

    const payload = {
        stock_code: form.stock_code,
        stock_name: form.stock_name,
        entry_date: toYmd(form.entry_date_ui),
        entry_price: form.entry_price === '' ? null : Number(form.entry_price),
        hold_qty: form.hold_qty === '' ? null : Number(form.hold_qty),
        memo: form.memo,
        enabled_flag: form.enabled_flag,
    };

    isSaving.value = true;
    try {
        if (popup.isEdit) {
            await aibeesApi.put(`/api/v1/sell-requests/${form.stock_code}`, payload);
        } else {
            await aibeesApi.post('/api/v1/sell-requests', payload);
        }
        closePopup();
        await fetchSellList();
    } finally {
        isSaving.value = false;
    }
};

/* ── 삭제 ── */
const removeRow = async (row) => {
    if (!confirm(`'${row.stock_name}' 종목을 삭제하시겠습니까?`)) return;
    await aibeesApi.delete(`/api/v1/sell-requests/${row.stock_code}`);
    await fetchSellList();
};

/* ── 종목 검색 layered popup (SAutoInput 응용) ── */
const stockSearch = reactive({
    visible: false,
    keyword: '',
    list: [],
    loading: false,
    searched: false,
});
const searchInputRef = ref(null);

const openStockSearch = () => {
    if (popup.isEdit) return; // 수정 시 종목코드(PK) 변경 불가
    stockSearch.keyword = '';
    stockSearch.list = [];
    stockSearch.searched = false;
    stockSearch.visible = true;
    nextTick(() => searchInputRef.value?.focus());
};

const closeStockSearch = () => { stockSearch.visible = false; };

const runStockSearch = async () => {
    const kw = stockSearch.keyword.trim();
    if (kw.length < 1) {
        alert('검색어를 입력해 주세요.');
        return;
    }
    stockSearch.loading = true;
    try {
        const { data } = await aibeesApi.get('/api/v1/stocks/search', {
            params: { searchTxt: kw }
        });
        const list = data.data ?? [];
        list.forEach(d => { d.type = d.stock_type_yf === 'KQ' ? '코스닥' : '코스피'; });
        stockSearch.list = list;
        stockSearch.searched = true;
    } finally {
        stockSearch.loading = false;
    }
};

const pickStock = (data) => {
    form.stock_code = data.stock_code;
    form.stock_name = data.stock_name;
    closeStockSearch();
};

/* ── 포맷 헬퍼 ── */
const formatDate = (ymd) => (ymd && ymd.length === 8)
    ? `${ymd.slice(0, 4)}.${ymd.slice(4, 6)}.${ymd.slice(6, 8)}` : '-';
const formatNumber = (v) => (v === null || v === undefined || v === '')
    ? '-' : Number(v).toLocaleString();
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

#sell-request {
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

    @media (max-width: 600px) {
        flex-direction: column;
        align-items: flex-start;
        gap: 12px;
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
    white-space: nowrap;
    transition: background .15s;

    &:hover {
        background: darken(#1c3d6e, 6%);
    }

    &:disabled {
        background: $gray-200;
        color: $gray-400;
        cursor: not-allowed;
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

.sell-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.83rem;
    text-align: center;

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
        white-space: nowrap;
        text-align: center;
    }

    td {
        padding: 10px 12px;
        border-bottom: 1px solid $gray-100;
        border-right: 1px solid $gray-100;
        vertical-align: middle;
        color: $gray-700;
        // text-align: center;

        &.num {
            text-align: right;
            font-variant-numeric: tabular-nums;
        }
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

.col-code { width: 110px; }
.col-name {
    min-width: 140px;
    text-align: left;
}
.col-date { width: 120px; }
.col-price { width: 120px; }
.col-qty { width: 100px; }
.col-memo { min-width: 160px; }
.col-flag { width: 60px; text-align: center; }
.col-action { width: 130px; text-align: right; }

.action-group {
    display: flex;
    gap: 6px;
    justify-content: flex-end;
}

/* chips / text */
.code-chip {
    font-size: 0.72rem;
    font-weight: 600;
    background: $gray-100;
    color: $gray-700;
    padding: 2px 7px;
    border-radius: 0.3rem;
    border: 1px solid $gray-200;
    font-family: 'SFMono-Regular', Consolas, monospace;
}

.memo-text {
    font-size: 0.8rem;
    color: $gray-500;
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

    &.active { background: $green; }
    &.inactive { background: $gray-200; }

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

    &.active .toggle-knob { left: 19px; }
    &.inactive .toggle-knob { left: 3px; }
}

.btn-edit,
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

.btn-delete:hover {
    border-color: $red;
    color: $red;
}

/* skeleton */
.loader-rows { padding: 8px; }

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

/* ── Mobile List ── */
.mobile-list {
    display: none;

    @media (max-width: 860px) {
        display: block;
    }
}

.sell-ul {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 10px;
}

.sell-li {
    background: $white;
    border: 1px solid $gray-200;
    border-radius: 0.6rem;
    padding: 14px;

    &.li-disabled { opacity: .55; }
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
        width: 52px;
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

    &.layer-top {
        z-index: 2100;
    }
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

.search-panel {
    max-width: 480px;
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

        &:hover { color: $gray-900; }
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

        &.full { grid-column: 1 / -1; }

        label {
            font-size: 0.78rem;
            font-weight: 600;
            color: $gray-700;
        }

        .req {
            color: $red;
            margin-left: 2px;
        }

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

            &:focus { border-color: $blue; }

            &:disabled,
            &[readonly] {
                background: $gray-50;
                color: $gray-700;
            }

            &::placeholder { color: $gray-400; }
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

/* 종목 선택 인풋 + 버튼 */
.stock-picker {
    display: flex;
    gap: 8px;

    .stock-display {
        flex: 1;
    }

    .btn-pick {
        flex-shrink: 0;
        padding: 8px 14px;
        border: 1px solid $navy;
        border-radius: 0.4rem;
        background: $white;
        color: $navy;
        font-size: 0.82rem;
        font-weight: 700;
        cursor: pointer;
        font-family: inherit;
        white-space: nowrap;
        transition: background .12s;

        &:hover { background: #f0f4ff; }

        &:disabled {
            border-color: $gray-200;
            color: $gray-400;
            cursor: not-allowed;
        }
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

        &:hover { border-color: $gray-400; }
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

        &:hover { background: darken(#1c3d6e, 6%); }

        &:disabled {
            opacity: .55;
            cursor: not-allowed;
        }
    }
}

/* ── 종목 검색 layered popup 내부 ── */
.search-bar {
    display: flex;
    gap: 8px;
    margin-bottom: 14px;

    input {
        flex: 1;
        padding: 9px 12px;
        border: 1px solid $gray-200;
        border-radius: 0.4rem;
        font-size: 0.86rem;
        color: $gray-900;
        font-family: inherit;
        outline: none;
        transition: border-color .15s;

        &:focus { border-color: $blue; }

        &::placeholder { color: $gray-400; }
    }

    .btn-search {
        flex-shrink: 0;
        padding: 9px 18px;
        border: none;
        border-radius: 0.4rem;
        background: $navy;
        color: $white;
        font-size: 0.84rem;
        font-weight: 700;
        cursor: pointer;
        font-family: inherit;
        white-space: nowrap;
        transition: background .15s;

        &:hover { background: darken(#1c3d6e, 6%); }

        &:disabled {
            opacity: .55;
            cursor: not-allowed;
        }
    }
}

.search-result {
    border: 1px solid $gray-200;
    border-radius: 0.5rem;
    overflow: hidden;

    ul {
        list-style: none;
        margin: 0;
        padding: 0;
    }

    li {
        display: flex;
        align-items: center;

        .item {
            padding: 9px 12px;
            font-size: 0.84rem;
        }

        .s_code {
            width: 80px;
            font-family: 'SFMono-Regular', Consolas, monospace;
            color: $gray-700;
        }

        .s_name {
            flex: 1;
            color: $gray-900;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .s_type {
            width: 64px;
            text-align: center;
            color: $gray-500;
            font-size: 0.78rem;
        }
    }

    .result-header {
        background: $gray-50;
        border-bottom: 1px solid $gray-200;

        .item {
            font-size: 0.72rem;
            font-weight: 700;
            color: $gray-500;
        }
    }

    .result-list {
        max-height: 320px;
        overflow-y: auto;

        &::-webkit-scrollbar { width: 6px; }
        &::-webkit-scrollbar-thumb {
            background: $gray-200;
            border-radius: 3px;
        }

        .result-item {
            cursor: pointer;
            border-bottom: 1px solid $gray-100;
            transition: background .12s;

            &:last-child { border-bottom: none; }

            &:hover { background: #f0f4ff; }
        }

        .result-empty {
            display: block;
            text-align: center;
            padding: 30px 0;
            color: $gray-400;
            font-size: 0.84rem;
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
    0%, 100% { opacity: .5; }
    50% { opacity: .9; }
}
</style>
