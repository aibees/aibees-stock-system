<template>
    <CBodyArea type="mobile">
    <div id="stock-theme-mobile">
        <div class="search-div">
            <div class="search-item">
                <SLabelInput id="search-date" label="일자" type="date" v-model="searchParam.date" />
            </div>
            <div class="search-item">
                <SLabelInput id="search-batchCode" label="테마명" type="text" v-model="searchParam.themeName" />
            </div>
            <div class="buttons-div">
                <button @click="getThemeList">
                    <font-awesome-icons :icon="['fa-solid', 'fa-magnifying-glass']" />
                </button>
            </div>
        </div>
    </div>
    <div id="stock-theme-list-mobile">
        <ul class="table-mobile header">
            <li class="lines" style="border-left: none;">
                <div class="list-item">
                    <div class="left">
                        <div class="h-item">테마명(테마코드)</div>
                    </div>
                    <div class="center">
                        <div class="h-item">등락율</div>
                    </div>
                    <div class="right">
                        <div class="h-item">3일 평균</div>
                    </div>
                </div>
            </li>
        </ul>
        <div class="body-wrapper">
            <ul class="table-mobile body" v-for="(data, idx) in themeList" :key="idx" :id=data.theme_code>
                <li class="lines" 
                    :style="{ borderLeftColor: data.per_flow === 'UP' ? '#d70404' : '#2828ff' }"
                    >
                    <div class="list-item">
                        <div class="left">
                            <div class="item">
                                <!-- <input class="left-input" :id="`batchCode_${idx}`" v-model="data.batch_code" @change="check_trx(idx)" /> -->
                                <a @click="goToDetail(data.theme_code)" style="cursor:pointer">{{ data.theme_name }} ({{
                                    data.theme_code }})</a>
                            </div>
                        </div>
                        <!-- <div class="percent"> -->
                            <div class="center">
                                <div class="item"
                                    :style="{ color: data.per_flow === 'UP' ? '#ff2b2b' : (data.per_flow === 'DOWN' ? '#d4d4ff' : '') }"
                                    >
                                    <div>
                                        <img :src="data.per_flow === 'UP' ? '/src/img/upper_arrow.png' : (data.per_flow === 'DOWN' ? '/src/img/lower_arrow.png' : '')" />
                                    </div>
                                    {{ data.per_today }} %
                                </div>
                            </div>
                            <div class="right">
                                <div class="item"
                                    :style="{ color: data.three_day_avg >= 0 ? '#ff2b2b' : '#d4d4ff' }"
                                    >
                                    <div>
                                        <img :src="data.three_day_avg >= 0 ? '/src/img/upper_arrow.png' : '/src/img/lower_arrow.png'" />
                                    </div>
                                    {{ data.three_day_avg }} %
                                </div>
                            </div>
                        <!-- </div> -->
                    </div>
                </li>
            </ul>
        </div>
    </div>
    </CBodyArea>
</template>

<script setup>
    import { onMounted, reactive, ref } from 'vue';
    import SLabelInput from '../../common/comp/SLabelInput.vue'
    import aibeesApi from '../../../scripts/aibeesApi.js'
    import { useRouter } from 'vue-router'

    /**
     * global variation
     */
     const router = useRouter();
     const themeList = ref([])
    const searchParam = reactive({
        themeName: '',
        date: ''
    });

    /**
     * life cycle
     */
    onMounted(() => {
        const today = new Date();
        const yyyy = today.getFullYear();
        const mm = String(today.getMonth() + 1).padStart(2, '0'); // 월: 0부터 시작하므로 +1
        const dd = String(today.getDate()).padStart(2, '0');

        searchParam.date = `${yyyy}-${mm}-${dd}`;
        getThemeList();
    })

    /**
     * vue functions
     */
    const getThemeList = async () => {
        const param = {
            'ymd': searchParam.date.replaceAll('-', ''),
            'themeName': searchParam.themeName
        }

        const { data } = await aibeesApi.get('/api/v1/themes', { params: param });
        themeList.value = data.data;
        themeList.value.forEach(t => {
            t.per_today = Number(t.per_today).toFixed(2);
            t.three_day_avg = Number(t.three_day_avg).toFixed(2);
        })
    }

    const goToDetail = (theme_code) => {
        router.push({
            name: 'stock-detail',
            query: {
                theme_code: theme_code,
                ymd: searchParam.date
            }
        });
    }

</script>
<style lang="scss" src="@@/stocks/Theme-List-Mobile.scss" scoped>
</style>

