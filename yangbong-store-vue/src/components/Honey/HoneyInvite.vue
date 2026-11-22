<template>
    <div id="honey-invite">
        <BrandHeader title="친구 초대" :back="HONEY_PATH" />
        <main class="hi">
            <section class="hero">
                <p class="k">친구 초대</p>
                <h1>친구와 함께<br />꿀을 모아요</h1>
                <div class="ill" aria-hidden="true">
                    <img class="jar" src="/img/emoji/honey.png" alt="" />
                    <img class="bee b1" src="/img/emoji/bee.png" alt="" />
                    <img class="bee b2" src="/img/emoji/bee.png" alt="" />
                </div>
            </section>

            <div class="rw">
                <div><b>+{{ reward.inviter }}</b><small>나</small></div>
                <div><b>+{{ reward.invitee }}</b><small>친구</small></div>
            </div>
            <ol class="how">
                <li><i>1</i>내 초대 코드를 친구에게 보내요</li>
                <li><i>2</i>친구가 가입하고 코드를 넣어요</li>
                <li><i>3</i>친구가 {{ reward.days }}일 방문하면 둘 다 꿀을 받아요</li>
            </ol>

            <section v-if="!loggedIn" class="guest">
                <button type="button" class="btn" @click="router.push('/login')">로그인하고 내 초대 코드 받기</button>
            </section>
            <p v-else-if="!inv && loading" class="msg">불러오고 있어요</p>
            <p v-else-if="!inv" class="msg">초대 정보를 불러오지 못했어요. 잠시 후 다시 열어 주세요.</p>
            <template v-else>
                <div class="code"><b>{{ inv.code }}</b><button type="button" @click="copy">{{ copied ? '복사했어요' : '복사' }}</button></div>
                <button type="button" class="btn" @click="share">초대 링크 보내기</button>
                <p class="stat">초대한 친구 <b>{{ inv.completed }}명</b><template v-if="inv.pending"> · 방문 기다리는 친구 {{ inv.pending }}명</template><br />이번 달 {{ inv.monthLeft }}명 더 꿀을 받을 수 있어요</p>

                <!-- 내가 받은 코드 -->
                <section v-if="inv.mine" class="mine">
                    <p class="t">등록한 초대 코드 <b>{{ inv.mine.code }}</b></p>
                    <p v-if="inv.mine.completed" class="d">꿀 +{{ reward.invitee }}을 받았어요</p>
                    <template v-else>
                        <p class="d">{{ inv.mine.goal }}일 중 {{ inv.mine.days }}일 방문했어요</p>
                        <span class="bar"><i :style="{ width: (inv.mine.days / inv.mine.goal * 100) + '%' }"></i></span>
                    </template>
                </section>
                <section v-else-if="inv.canRedeem" class="enter">
                    <button v-if="!entering" type="button" class="link" @click="entering = true">초대 코드를 받았나요? <b>코드 입력하기 ›</b></button>
                    <form v-else class="form" @submit.prevent="redeem">
                        <label for="invite-code">받은 초대 코드</label>
                        <div class="row">
                            <input id="invite-code" v-model.trim="codeInput" maxlength="12" autocomplete="off" autocapitalize="characters" placeholder="예) 7692B7FB" />
                            <button type="submit" :disabled="!codeInput || honey.busy">등록</button>
                        </div>
                        <p v-if="error" class="err" role="alert">{{ error }}</p>
                    </form>
                </section>
            </template>
        </main>
    </div>
</template>

<script setup>
/** 친구 초대(꿀 2단계). 기획: docs/points-plan.md · 서버: router_honey /honey/invite */
import { useHoneyStore } from '@scripts/stores/honey-store.js';
import { assUserSession } from '@scripts/stores/user-stores.js';
import { HONEY_PATH } from '@scripts/support.js';

const SITE_URL = 'https://yangbong-store.chagoklabs.com/';
const router = useRouter();
const honey = useHoneyStore();
const loggedIn = computed(() => !!assUserSession().user.accessToken);
const inv = computed(() => honey.invite);
const loading = ref(false);
const reward = computed(() => inv.value?.reward ?? { inviter: 300, invitee: 100, days: 3 });
const copied = ref(false);
const entering = ref(false);
const codeInput = ref('');
const error = ref('');

const shareText = () => `양봉상회에서 같이 주식 공부하고 꿀 모아요!\n초대 코드: ${inv.value.code}\n가입하고 '꿀 모으기 > 친구 초대'에 코드를 넣은 뒤 ${reward.value.days}일 방문하면 꿀 ${reward.value.invitee}을 드려요.\n${SITE_URL}`;
const copy = async () => {
    try { await navigator.clipboard.writeText(inv.value.code); copied.value = true; setTimeout(() => { copied.value = false; }, 2000); } catch { /* 주소는 화면에 보인다 */ }
};
const share = async () => {
    const text = shareText();
    if (navigator.share) {
        try { await navigator.share({ title: '양봉상회 친구 초대', text }); return; } catch (e) { if (e?.name === 'AbortError') return; }
    }
    try { await navigator.clipboard.writeText(text); copied.value = true; setTimeout(() => { copied.value = false; }, 2000); } catch { /* 복사 불가 환경 */ }
};
const redeem = async () => {
    error.value = '';
    const r = await honey.redeemInvite(codeInput.value);
    if (r !== true) error.value = r;
};
onMounted(async () => {
    if (!loggedIn.value) return;
    loading.value = true;
    await honey.loadInvite();
    loading.value = false;
});
</script>

<style scoped lang="scss">
@use '@@/_home-tokens.scss' as *;

#honey-invite { min-height: 100vh; background: $card; color: $ink; text-align: left; font-family: $font-body; letter-spacing: -0.2px; }
button { font: inherit; letter-spacing: inherit; cursor: pointer; border: 0; }
.hi { max-width: 520px; margin: 0 auto; padding: 4px $pad-x 40px; box-sizing: border-box; }
.hero { text-align: center; padding-top: 4px;
    .k { margin: 0; font-size: 14px; font-weight: 800; color: $amber-700; }
    h1 { margin: 6px 0 0; font-size: 28px; line-height: 1.3; letter-spacing: -.8px; }
    .ill { position: relative; height: 160px; margin: 14px auto 6px; width: 220px; }
    .jar { position: absolute; left: 40px; top: 30px; width: 110px; height: 110px; }
    .bee { position: absolute; } .b1 { left: 140px; top: 6px; width: 72px; height: 72px; } .b2 { left: 128px; top: 92px; width: 50px; height: 50px; transform: scaleX(-1); }
}
.rw { display: flex; gap: 10px; div { flex: 1; padding: 14px 10px; border-radius: 14px; background: $honey-strip; text-align: center; } b { display: block; font-size: 22px; color: $honey-ink; } small { font-size: 12.5px; color: #7A5A1E; } }
.how { margin: 16px 0 0; padding: 0; list-style: none;
    li { display: flex; gap: 10px; padding: 7px 0; font-size: 14px; color: $sub-ink; }
    i { font-style: normal; width: 22px; height: 22px; flex: none; border-radius: 7px; background: $honey-100; color: $amber-700; font-weight: 800; font-size: 12px; display: flex; align-items: center; justify-content: center; } }
.msg { padding: 24px 0; text-align: center; font-size: 14px; color: $sub; }
.guest { margin-top: 16px; }
.btn { width: 100%; height: 52px; margin-top: 10px; border-radius: $radius; background: #5A3C08; color: #fff; font-size: 16px; font-weight: 700; }
.code { margin-top: 16px; height: 58px; border-radius: 14px; border: 1.5px solid $honey-300; display: flex; align-items: center; justify-content: space-between; padding: 0 8px 0 18px;
    b { font-size: 20px; letter-spacing: 2px; } button { height: 40px; padding: 0 14px; border-radius: 10px; background: $honey-100; color: $amber-700; font-weight: 700; font-size: 14px; } }
.stat { margin: 12px 0 0; text-align: center; font-size: 13px; color: $sub-ink; line-height: 1.6; word-break: keep-all; b { color: $ink; } }
.mine { margin-top: 18px; padding: 14px 16px; border-radius: 14px; border: 1px solid $line;
    .t { margin: 0; font-size: 14px; color: $sub-ink; b { color: $ink; letter-spacing: 1px; } } .d { margin: 4px 0 0; font-size: 15px; font-weight: 700; }
    .bar { display: block; margin-top: 10px; height: 7px; border-radius: 4px; background: #FFEFC4; overflow: hidden; i { display: block; height: 100%; background: $honey-500; } } }
.enter { margin-top: 18px; text-align: center; }
.link { background: transparent; font-size: 13.5px; color: $sub-ink; b { color: $amber-700; } }
.form { text-align: left; label { font-size: 13px; font-weight: 700; color: $sub-ink; }
    .row { display: flex; gap: 8px; margin-top: 6px; }
    input { flex: 1; min-width: 0; height: 48px; padding: 0 14px; border: 1.5px solid $line; border-radius: 12px; font: inherit; font-size: 16px; letter-spacing: 1.5px; text-transform: uppercase; }
    .row button { flex: none; height: 48px; padding: 0 18px; border-radius: 12px; background: #5A3C08; color: #fff; font-weight: 700; &:disabled { opacity: .5; } }
    .err { margin: 8px 0 0; font-size: 13px; color: $up; } }
</style>
