<template>
    <div id="batch-log-setting">
        <Headers :prop_title="title" />

        <div class="contents">

            <!-- ── 상단 타이틀 ── -->
            <section class="head-desc">
                <div class="head-left">
                    <h2>배치 실행 로그</h2>
                    <p class="sub-text">실행된 배치 작업의 결과를 조회합니다 (최신 batch_seq 순)</p>
                </div>
                <div class="head-right">
                    <button class="btn-refresh" @click="fetchLogList">
                        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none"
                            stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M23 4v6h-6" />
                            <path d="M1 20v-6h6" />
                            <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10" />
                            <path d="M20.49 15a9 9 0 0 1-14.85 3.36L1 14" />
                        </svg>
                        새로고침
                    </button>
                </div>
            </section>

            <!-- ── 데스크탑 테이블 ── -->
            <section class="table-section">
                <div v-if="isLoading" class="loader-rows">
                    <div v-for="n in 6" :key="n" class="skeleton-row"></div>
                </div>

                <table v-else class="log-table">
                    <thead>
                        <tr>
                            <th class="col-seq">SEQ</th>
                            <th class="col-code">배치 코드</th>
                            <th class="col-cnt">처리건수</th>
                            <th class="col-status">상태</th>
                            <th class="col-time">시작시간</th>
                            <th class="col-time">종료시간</th>
                            <th class="col-desc">설명</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr v-for="row in logList" :key="row.batch_seq">
                            <td class="col-seq"><span class="code-chip">{{ row.batch_seq }}</span></td>
                            <td class="col-code"><span class="comp-text">{{ row.batch_code }}</span></td>
                            <td class="col-cnt">{{ row.batch_cnt ?? '-' }}</td>
                            <td class="col-status">
                                <span :class="['status-badge', statusClass(row.status)]">{{ row.status ?? '-'
                                }}</span>
                            </td>
                            <td class="col-time">{{ row.start_time ?? '-' }}</td>
                            <td class="col-time">{{ row.end_time ?? '-' }}</td>
                            <td class="col-desc">{{ row.desc ?? '-' }}</td>
                        </tr>
                        <tr v-if="!isLoading && logList.length === 0">
                            <td colspan="7" class="empty-cell">조회된 배치 로그가 없습니다.</td>
                        </tr>
                    </tbody>
                </table>
            </section>

            <!-- ── 모바일 리스트 (ul/li) ── -->
            <section class="mobile-list">
                <div v-if="isLoading" class="loader-rows">
                    <div v-for="n in 4" :key="n" class="skeleton-row"></div>
                </div>

                <ul v-else class="log-ul">
                    <li v-for="row in logList" :key="row.batch_seq" class="log-li">
                        <div class="li-top">
                            <span class="code-chip">#{{ row.batch_seq }}</span>
                            <span :class="['status-badge', statusClass(row.status)]">{{ row.status ?? '-' }}</span>
                        </div>
                        <div class="li-name">{{ row.batch_code }}</div>
                        <div class="li-row">
                            <span class="li-label">처리건수</span>
                            <span>{{ row.batch_cnt ?? '-' }}</span>
                        </div>
                        <div class="li-row">
                            <span class="li-label">시작</span>
                            <span>{{ row.start_time ?? '-' }}</span>
                        </div>
                        <div class="li-row">
                            <span class="li-label">종료</span>
                            <span>{{ row.end_time ?? '-' }}</span>
                        </div>
                        <div class="li-row" v-if="row.desc">
                            <span class="li-label">설명</span>
                            <span>{{ row.desc }}</span>
                        </div>
                    </li>
                    <li v-if="logList.length === 0" class="empty-cell">조회된 배치 로그가 없습니다.</li>
                </ul>
            </section>

            <!-- ── 페이지네이션 ── -->
            <section class="pagination" v-if="!isLoading && totalPages > 0">
                <button class="page-btn" @click="goPage(0)" :disabled="page === 0">처음</button>
                <button class="page-btn" @click="goPage(page - 1)" :disabled="page === 0">이전</button>
                <span class="page-info">{{ page + 1 }} / {{ totalPages }}</span>
                <button class="page-btn" @click="goPage(page + 1)" :disabled="page >= totalPages - 1">다음</button>
                <button class="page-btn" @click="goPage(totalPages - 1)" :disabled="page >= totalPages - 1">마지막</button>
            </section>
        </div>
    </div>
</template>

<script setup>
import aibeesApi from '@scripts/aibeesApi.js';
import Lnb from '../common/Lnb.vue';

const title = ref('배치 로그');

/* ── 목록/페이징 ── */
const logList = ref([]);
const isLoading = ref(true);
const page = ref(0);
const size = ref(20);
const totalPages = ref(0);

const fetchLogList = async () => {
    isLoading.value = true;
    try {
        const { data } = await aibeesApi.get('/api/v1/batch-logs', {
            params: {
                page: page.value,
                size: size.value,
                sort: 'batch_seq,desc'
            }
        });
        logList.value = data.data ?? [];
        totalPages.value = data.totalPages ?? 0;
    } finally {
        isLoading.value = false;
    }
};

const goPage = (target) => {
    if (target < 0 || target > totalPages.value - 1) return;
    page.value = target;
    fetchLogList();
};

const statusClass = (status) => {
    switch (status) {
        case 'SUCCESS':
        case 'DONE':
        case 'COMPLETE':
            return 'success';
        case 'FAIL':
        case 'ERROR':
            return 'fail';
        case 'RUNNING':
            return 'running';
        default:
            return 'default';
    }
};

onMounted(async () => {
    await fetchLogList();
});
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

#batch-log-setting {
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

.btn-refresh {
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

.log-table {
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
        white-space: nowrap;
    }

    tbody tr:last-child td {
        border-bottom: none;
    }

    tbody tr:hover td {
        background: $gray-50;
    }
}

/* column widths */
.col-seq {
    width: 90px;
}

.col-code {
    min-width: 180px;
}

.col-cnt {
    width: 90px;
    text-align: right;
}

.col-status {
    width: 100px;
    text-align: center;
}

.col-time {
    width: 160px;
}

.col-desc {
    min-width: 220px;
    white-space: normal !important;
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
}

.comp-text {
    font-family: 'SFMono-Regular', Consolas, monospace;
    font-size: 0.78rem;
    color: $gray-700;
}

/* status badge */
.status-badge {
    font-size: 0.7rem;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 0.3rem;
    white-space: nowrap;

    &.success {
        background: #d3f9d8;
        color: $green;
        border: 1px solid #8ce99a;
    }

    &.fail {
        background: #ffe3e3;
        color: $red;
        border: 1px solid #ffa8a8;
    }

    &.running {
        background: #fff0b3;
        color: $amber;
        border: 1px solid #ffd43b;
    }

    &.default {
        background: $gray-100;
        color: $gray-500;
        border: 1px solid $gray-200;
    }
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

.log-ul {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 10px;
}

.log-li {
    background: $white;
    border: 1px solid $gray-200;
    border-radius: 0.6rem;
    padding: 14px;
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
    font-family: 'SFMono-Regular', Consolas, monospace;
}

.li-row {
    display: flex;
    gap: 8px;
    align-items: flex-start;
    font-size: 0.8rem;
    margin-bottom: 4px;
    color: $gray-700;

    .li-label {
        flex-shrink: 0;
        width: 56px;
        color: $gray-500;
        font-weight: 600;
    }
}

/* ── Pagination ── */
.pagination {
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 8px;
    margin-top: 18px;
}

.page-btn {
    padding: 6px 14px;
    border: 1px solid $gray-200;
    border-radius: 0.4rem;
    background: $white;
    color: $gray-700;
    font-size: 0.8rem;
    font-weight: 600;
    cursor: pointer;
    font-family: inherit;
    transition: border-color .12s, color .12s;

    &:hover:not(:disabled) {
        border-color: $blue;
        color: $blue;
    }

    &:disabled {
        opacity: .45;
        cursor: not-allowed;
    }
}

.page-info {
    font-size: 0.82rem;
    font-weight: 600;
    color: $gray-700;
    padding: 0 6px;
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
