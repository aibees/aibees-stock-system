<template>
    <div id="issue-detail">
        <BrandHeader title="오늘의 경제 이슈" back="/home" />
        <main class="id">
            <p v-if="loading" class="msg">불러오고 있어요</p>
            <p v-else-if="!issue" class="msg">아직 공개된 이슈가 없어요.</p>
            <template v-else>
                <p class="date">{{ dateText }} · 매일 아침 바뀌어요</p>
                <div v-if="issue.keywords.length" class="kw"><span v-for="k in issue.keywords" :key="k">#{{ k }}</span></div>
                <h1>{{ issue.title }}</h1>

                <section v-if="issue.what" class="blk">
                    <h2>무슨 일이 있었나요</h2>
                    <p>{{ issue.what }}</p>
                </section>
                <section v-if="issue.why.length" class="blk">
                    <h2>왜 중요할까요</h2>
                    <ul><li v-for="w in issue.why" :key="w">{{ w }}</li></ul>
                </section>
                <div v-if="issue.term" class="term">
                    <b>알아두면 좋은 말 · {{ issue.term.name }}</b>
                    <span>{{ issue.term.desc }}</span>
                </div>

                <!-- 오늘 강했던 업종 TOP 3(2026-11-22 홈에서 이리로): 이슈를 만들 때의 업종 등락(시가총액 가중) -->
                <section v-if="issue.sectors.length" class="top3">
                    <div class="t-head"><h2>오늘 강했던 업종 TOP 3</h2><span v-if="issue.sectorYmd">{{ shortDate(issue.sectorYmd) }} 종가 기준</span></div>
                    <ol>
                        <li v-for="(s, i) in issue.sectors" :key="s.market + s.sector_cd">
                            <div class="r">
                                <span class="n">{{ i + 1 }}</span>
                                <span class="nm">{{ s.sector_name }}<small>{{ s.market === 'KOSPI' ? '코스피' : '코스닥' }}</small></span>
                                <span class="badge" :class="s.chg_rate > 0 ? 'up' : (s.chg_rate < 0 ? 'down' : 'flat')">{{ pct(s.chg_rate) }}</span>
                            </div>
                            <p v-if="s.leaders?.length" class="ld">대표 종목 · {{ s.leaders.join(' · ') }}</p>
                            <p v-if="s.why" class="why">{{ s.why }}</p>
                        </li>
                    </ol>
                    <p class="t-note">업종에 속한 회사 주가를 시가총액으로 묶어 계산해요.</p>
                </section>

                <section v-if="issue.sources.length" class="src">
                    <h2>관련 기사 <small>원문으로 이동</small></h2>
                    <a v-for="s in issue.sources" :key="s.url" :href="s.url" target="_blank" rel="noopener noreferrer">
                        <span>{{ s.title }}</span><small>{{ s.press }} ›</small>
                    </a>
                </section>

                <section v-if="past.length" class="past">
                    <h2>지난 이슈</h2>
                    <button v-for="p in past" :key="p.ymd" type="button" @click="open(p.ymd)">
                        <small>{{ shortDate(p.ymd) }}</small><span>{{ p.title }}</span>
                    </button>
                </section>

                <p class="note">기사 내용을 쉽게 다시 정리한 거예요. 정확한 내용은 원문 기사를 확인해 주세요. 특정 종목을 사거나 팔라는 뜻이 아니에요.</p>
            </template>
        </main>
    </div>
</template>

<script setup>
/** 오늘의 경제 이슈 상세 — 서버: router_daily_issue(공개된 것만). /issue = 최근, /issue/YYYYMMDD = 그날 */
import aibeesApi from '@scripts/aibeesApi.js';
import { issueDateText, shortDate } from './issueText.js';

const route = useRoute();
const router = useRouter();
const issue = ref(null);
const past = ref([]);
const loading = ref(true);
const dateText = computed(() => issueDateText(issue.value?.ymd));
const pct = (n) => `${n > 0 ? '+' : (n < 0 ? '−' : '')}${Math.abs(n).toFixed(1)}%`;

const load = async () => {
    loading.value = true;
    try {
        const ymd = route.params.ymd;
        const { data } = await aibeesApi.get('/api/v1/daily-issue');
        past.value = data?.data?.past ?? [];
        if (ymd && ymd !== data?.data?.issue?.ymd) {
            const r = await aibeesApi.get(`/api/v1/daily-issue/${ymd}`, { silentError: true });
            issue.value = r.data?.data ?? null;
        } else {
            issue.value = data?.data?.issue ?? null;
        }
        if (issue.value) past.value = past.value.filter(p => p.ymd !== issue.value.ymd);
    } catch {
        issue.value = null;
    } finally {
        loading.value = false;
    }
};
const open = (ymd) => { router.push(`/issue/${ymd}`); };
watch(() => route.params.ymd, () => { load(); window.scrollTo(0, 0); });
onMounted(load);
</script>

<style scoped lang="scss">
@use '@@/_home-tokens.scss' as *;

#issue-detail { min-height: 100vh; background: $card; color: $ink; text-align: left; font-family: $font-body; letter-spacing: -0.2px; }
button { font: inherit; letter-spacing: inherit; cursor: pointer; border: 0; background: transparent; color: inherit; text-align: left; }
h2 { margin: 0; }
.id { max-width: 640px; margin: 0 auto; padding: 8px $pad-x 48px; box-sizing: border-box; }
.msg { padding: 48px 0; text-align: center; font-size: 14px; color: $sub; }
.date { margin: 0; font-size: 13px; color: $sub; }
.kw { display: flex; flex-wrap: wrap; gap: 6px; margin-top: $gap; span { padding: 2px 8px; border-radius: 8px; border: 1px solid $line; font-size: 12px; font-weight: 700; color: $sub-ink; } }
h1 { margin: $gap 0 0; font-size: 23px; line-height: 1.4; letter-spacing: -0.6px; word-break: keep-all; }
.blk { margin-top: $sec-pt; h2 { font-size: 14px; color: $amber-700; } p, li { margin: 6px 0 0; font-size: 15.5px; line-height: 1.65; color: $sub-ink; word-break: keep-all; } ul { margin: 0; padding-left: 18px; } }
.term { margin-top: $sec-pt; padding: $card-pad; border-radius: $radius; background: $honey-100; color: #5A3C08; font-size: 14.5px; line-height: 1.6; b { display: block; } }

.top3 { margin-top: $sec-pt * 1.5; padding-top: $sec-pt; border-top: 8px solid $bg; margin-left: -$pad-x; margin-right: -$pad-x; padding-left: $pad-x; padding-right: $pad-x;
    ol { margin: $head-gap 0 0; padding: 0; list-style: none; }
    li { padding: $gap 0; border-top: 1px solid $line; &:first-child { border-top: 0; padding-top: 0; } }
}
.t-head { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; h2 { font-size: 20px; letter-spacing: -0.5px; } span { font-size: 13px; color: $sub; white-space: nowrap; } }
.r { display: flex; align-items: center; gap: 12px; min-height: 32px; }
.n { width: 16px; font-weight: 800; color: $amber-700; }
.nm { flex: 1; min-width: 0; font-size: 16px; font-weight: 700; small { margin-left: 6px; font-size: 12px; font-weight: 500; color: $sub; } }
.ld { margin: 4px 0 0 28px; font-size: 13px; color: $sub; }
.why { margin: 6px 0 0 28px; font-size: 14.5px; line-height: 1.55; color: $sub-ink; word-break: keep-all; }
.t-note { margin: $gap 0 0; font-size: 12px; color: $sub; }

.src { margin-top: $sec-pt; padding-top: $sec-pt; border-top: 1px solid $line;
    h2 { font-size: 14px; color: $sub; small { font-weight: 400; } }
    a { display: flex; justify-content: space-between; gap: 12px; min-height: 48px; align-items: center; border-bottom: 1px solid $line; font-size: 14.5px; color: $ink; text-decoration: none; small { flex: none; color: $sub; } }
}
.past { margin-top: $sec-pt; h2 { font-size: 14px; }
    button { display: flex; gap: 12px; width: 100%; min-height: 44px; align-items: center; font-size: 14px; color: $sub-ink; small { flex: none; width: 40px; color: $sub; } span { flex: 1; min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; } }
}
.note { margin: $sec-pt 0 0; font-size: 12px; line-height: 1.6; color: $sub; }
.badge { flex: none; height: 26px; min-width: 60px; padding: 0 8px; border-radius: 8px; display: inline-flex; align-items: center; justify-content: center; font-size: 13.5px; font-weight: 700;
    &.up { color: $up; background: $up-bg; } &.down { color: $down; background: $down-bg; } &.flat { color: $sub; background: $bg; } }
</style>
