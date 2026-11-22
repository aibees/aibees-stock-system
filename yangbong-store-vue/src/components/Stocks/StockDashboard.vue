<template>
    <div id="stock-dashboard">
        <BrandHeader title="주식분석" />

        <main class="sd-main">

            <!-- ── 바로가기 ── -->
            <section class="sd-sec" aria-label="바로가기">
                <ul class="sd-list">
                    <li v-for="t in tiles" :key="t.path">
                        <button type="button" class="sd-tile" @click="router.push(t.path)">
                            <span class="sd-text">
                                <span class="sd-name">{{ t.name }}</span>
                                <span class="sd-desc">{{ t.desc }}</span>
                            </span>
                            <svg class="chev" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><path d="m9 6 6 6-6 6"></path></svg>
                        </button>
                    </li>
                </ul>
            </section>

            <!-- ── 내 설정: 지금 적용 중인 값. 홈·매수추천의 회사 선별과 순서가 이걸 따른다 ── -->
            <section class="sd-sec" aria-labelledby="sd-set-title">
                <div class="sd-head">
                    <h2 id="sd-set-title">내 설정</h2>
                    <button type="button" class="sd-link" @click="router.push(PRESET_PATH)">설정 바꾸기</button>
                </div>
                <dl class="sd-settings">
                    <div class="sd-set"><dt>성향</dt><dd>{{ type.name }}</dd></div>
                    <div class="sd-set"><dt>충족 기준</dt><dd>{{ passRule }}</dd></div>
                    <div class="sd-set"><dt>회사 순서</dt><dd>{{ orderLabel(type.order) }}</dd></div>
                </dl>
                <h3 class="sd-sub">보조지표</h3>
                <ul class="sd-ind">
                    <li v-for="r in indRows" :key="r.key" :class="{ off: !r.text }">
                        <span class="sd-ind-name">{{ r.label }}</span>
                        <span class="sd-ind-val">{{ r.text || '사용 안 함' }}</span>
                    </li>
                </ul>
                <p v-if="!persona.decided" class="sd-hint">아직 성향을 정하지 않아 기본 설정(균형형)이 적용 중이에요.</p>
            </section>



            <!-- ── 최근 본 회사 ── -->
            <section class="sd-sec" aria-labelledby="sd-recent-title">
                <div class="sd-head">
                    <h2 id="sd-recent-title">최근 본 회사</h2>
                    <button v-if="recent.length" type="button" class="sd-link" @click="clear">지우기</button>
                </div>
                <p v-if="!recent.length" class="sd-empty">아직 본 회사가 없어요. AI 분석 종목에서 회사를 열어 보세요.</p>
                <ul v-else class="sd-recent">
                    <li v-for="r in recent" :key="r.code">
                        <button type="button" class="sd-recent-row" @click="openStock(r)">
                            <span class="sd-rname">{{ r.name }}</span>
                            <span class="sd-rcode">{{ r.code }}</span>
                            <span class="sd-rtime">{{ timeAgo(r.ts) }}</span>
                        </button>
                    </li>
                </ul>
            </section>
        </main>
    </div>
</template>

<script setup>
/**
 * 주식분석 대시보드 — 메뉴 목록이 아니라 이 그룹만의 첫 화면.
 *   1) 내 설정: 지금 적용 중인 성향·충족 기준·회사 순서와 보조지표별 수치
 *   2) 바로가기: 매수추천 · AI 분석 · 차트 확인 · 내 설정(권한 없는 항목은 서버 경로에 없어 빠진다)
 *   3) 최근 본 회사: 이 기기에서 AI 분석·차트·매수추천 상세를 연 회사(최근 10개)
 */
import { assUserSession } from '@scripts/stores/user-stores.js';
import { ensureAccess } from '@scripts/useAccess.js';
import { usePersonaStore } from '@scripts/stores/persona-store.js';
import { BASIC_INDICATORS, orderLabel, indicatorSummary, passRuleText } from '@scripts/indicators.js';
import { getRecent, clearRecent } from '@scripts/recentStocks.js';

const PRESET_PATH = '/stock/preset';
const router = useRouter();
const userSession = assUserSession();
const persona = usePersonaStore();
const type = computed(() => persona.currentType);
const passRule = computed(() => passRuleText(type.value.settings));
// 켠 지표는 수치와 함께, 끈 지표는 "사용 안 함"으로 — 지금 어떤 값이 적용 중인지 한눈에
const indRows = computed(() => BASIC_INDICATORS.map(d => ({ key: d.key, label: d.label, text: indicatorSummary(d.key, type.value.settings) }))
    .sort((a, b) => (a.text ? 0 : 1) - (b.text ? 0 : 1)));

const ALL = [
    { path: '/stock/buy-target', name: 'AI 분석 종목', desc: '내 설정에 맞는 회사를 순서대로 보여 드려요' },
    { path: '/stock/info',       name: 'AI 분석',  desc: '종목을 하나 골라 사업·재무·뉴스를 분석해 드려요' },
    { path: '/stock/chart',      name: '차트 확인', desc: '일·주·월봉과 이동평균선으로 차트를 살펴보세요' },
    { path: PRESET_PATH,         name: '내 설정',  desc: '보조지표를 켜고 끄고 수치를 직접 고쳐요', always: true },
];
const tiles = computed(() => ALL.filter(t => t.always || userSession.access.paths.includes(t.path)));

const recent = ref(getRecent());
const clear = () => { clearRecent(); recent.value = []; };
const openStock = (r) => router.push({ path: '/stock/info', query: { stock_code: r.code, stock_name: r.name } });
const timeAgo = (ts) => {
    const m = Math.floor((Date.now() - Number(ts || 0)) / 60000);
    if (m < 1) return '방금';
    if (m < 60) return `${m}분 전`;
    const h = Math.floor(m / 60);
    if (h < 24) return `${h}시간 전`;
    return `${Math.floor(h / 24)}일 전`;
};

onMounted(() => ensureAccess());
</script>

<style scoped lang="scss">
@use '@@/_home-tokens.scss' as *;

#stock-dashboard {
    min-height: 100vh;
    background: $card;
    color: $ink;
    text-align: left;
    font-family: $font-body;
}
.sd-main { max-width: 720px; margin: 0 auto; padding: 4px 0 24px; }
.sd-sec { padding-top: 16px; & + & { margin-top: 8px; border-top: 1px solid $line-soft; } }
.sd-head {
    display: flex; align-items: baseline; justify-content: space-between; gap: 8px; margin: 0 16px 6px;
    h2 { margin: 0; font-size: 17px; font-weight: 700; }
}
.sd-link {
    min-height: 32px; padding: 0 2px; border: 0; background: transparent; color: $accent;
    font: inherit; font-size: 13px; font-weight: 600; cursor: pointer; text-decoration: underline; text-underline-offset: 3px;
}
.down { color: $down; }

.sd-settings { margin: 0; padding: 0 16px; border-top: 1px solid $line-soft; }
.sd-set {
    display: flex; align-items: baseline; justify-content: space-between; gap: 12px;
    padding: 11px 0; border-bottom: 1px solid $line-soft;
    dt { font-size: 13px; color: $sub-2; flex: none; }
    dd { margin: 0; font-size: 15px; font-weight: 600; text-align: right; b { font-size: 17px; } }
}
.sd-sub { margin: 14px 16px 4px; font-size: 13px; font-weight: 700; color: $accent; }
.sd-ind { list-style: none; margin: 0; padding: 0 16px; border-top: 1px solid $line-soft; }
.sd-ind li {
    display: flex; align-items: baseline; justify-content: space-between; gap: 12px; padding: 9px 0; border-bottom: 1px solid $line-soft;
    .sd-ind-name { font-size: 14px; font-weight: 600; flex: none; }
    .sd-ind-val { font-size: 13px; color: $ink; text-align: right; }
    &.off .sd-ind-name { color: $sub-2; font-weight: 500; }
    &.off .sd-ind-val { color: $sub-2; }
}
.sd-hint { margin: 8px 16px 0; font-size: 12px; color: $sub-2; }

.sd-list { list-style: none; margin: 0; padding: 0; border-top: 1px solid $line-soft; li { border-bottom: 1px solid $line-soft; } }
.sd-tile {
    width: 100%; display: flex; align-items: center; justify-content: space-between; gap: 12px;
    min-height: 64px; padding: 12px 16px; box-sizing: border-box; border: 0; background: transparent;
    color: inherit; font: inherit; text-align: left; cursor: pointer; -webkit-tap-highlight-color: transparent;
    @media (hover: hover) { &:hover { background: #FFFDF3; } }
    &:active { background: $bar; }
}
.sd-text { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
.sd-name { font-size: 16px; font-weight: 700; }
.sd-desc { font-size: 13px; line-height: 1.4; color: $sub; }
.chev { color: $sub-2; flex-shrink: 0; }

.sd-empty { margin: 4px 16px 0; padding: 14px 0; font-size: 13px; line-height: 1.5; color: $sub; border-top: 1px solid $line-soft; }
.sd-recent { list-style: none; margin: 0; padding: 0; border-top: 1px solid $line-soft; li { border-bottom: 1px solid $line-soft; } }
.sd-recent-row {
    width: 100%; display: flex; align-items: baseline; gap: 8px; min-height: 48px; padding: 10px 16px; box-sizing: border-box;
    border: 0; background: transparent; color: inherit; font: inherit; text-align: left; cursor: pointer;
    @media (hover: hover) { &:hover { background: #FFFDF3; } }
    .sd-rname { font-size: 15px; font-weight: 600; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .sd-rcode { font-size: 12px; color: $sub-2; flex: none; }
    .sd-rtime { margin-left: auto; font-size: 12px; color: $sub-2; flex: none; }
}
</style>
