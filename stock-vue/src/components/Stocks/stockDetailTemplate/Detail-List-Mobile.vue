<template>
    <div id="stock-detail-mobile">
        <div class="search-div">
            <div class="div-flex search-item">
                <div class="code">
                    <SLabelInput 
                        id="search-code"
                        label="테마코드"
                        width="100%"
                        type="text"
                        align="center"
                        v-model="searchParam.theme_code"
                    />
                </div>
                <div class="name">
                    <select 
                        class="theme_select"
                        v-model="searchParam.theme_code"
                        @change="getThemeDetailList">
                        <option v-for="th in theme_list" :key="th.theme_code" :value="th.theme_code">
                            {{ th.theme_name }}
                        </option>
                    </select>
                </div>
            </div>
            <div class="search-item">
                <SLabelInput 
                    id="search-date"
                    label="일자"
                    type="date"
                    width="100%"
                    v-model="searchParam.date"
                    @change="getThemeList(searchParam.date)"
                />
            </div>
            <div class="buttons-div">
                <button @click="getThemeDetailList">
                    <font-awesome-icons :icon="['fa-solid', 'fa-magnifying-glass']" />
                </button>
            </div>
        </div>
    </div>
    <div id="stock-detail-list-mobile">
        <ul class="table-mobile header">
            <li class="lines">
                <div class="list-item">
                    <div class="left">
                        <div class="item">테마명(테마코드)</div>
                    </div>
                    <div class="center">
                        <div class="item">등락율</div>
                    </div>
                </div>
            </li>
        </ul>
        <div class="body-wrapper">
            <ul class="table-mobile body" v-for="(data, idx) in detail_list" :key="idx" :id=data.theme_code>
                <li class="lines" 
                    :style="{ borderLeftColor: data.per_flow === 'UP' ? '#d70404' : '#2828ff' }"
                    >
                    <div class="list-item">
                        <div class="left">
                            <div class="item">
                                <!-- <input class="left-input" :id="`batchCode_${idx}`" v-model="data.batch_code" @change="check_trx(idx)" /> -->
                                <a style="cursor:pointer">{{ data.stock_name }} ({{ data.stock_code }})</a>
                            </div>
                        </div>
                        <div class="center">
                                <div class="item"
                                    :style="{ color: data.per_flow === 'UP' ? '#ff2b2b' : (data.per_flow === 'DOWN' ? '#d4d4ff' : '') }"
                                    >
                                    <div>
                                        <img :src="data.per_flow === 'UP' ? '/src/img/upper_arrow.png' : (data.per_flow === 'DOWN' ? '/src/img/lower_arrow.png' : '')" />
                                    </div>
                                    {{ data.per_rate }} %
                                </div>
                        </div>
                    </div>
                </li>
            </ul>
        </div>
    </div>
</template>

<script setup>
    import { watch, onMounted, reactive, ref } from 'vue';
    import SLabelInput from '../../common/comp/SLabelInput.vue'
    import aibeesApi from '../../../scripts/aibeesApi.js'
    import { useRoute } from 'vue-router';

    const props = defineProps({ prop_search: Object });
    const theme_list = ref([]);
    const detail_list = ref([]);
    const searchParam = reactive({
        theme_code: '',
        theme_name: '',
        date: ''
    });
    
    const fetchMenu = async () => {
        const today = new Date();
        const yyyy = today.getFullYear();
        const mm = String(today.getMonth() + 1).padStart(2, '0'); // 월: 0부터 시작하므로 +1
        const dd = String(today.getDate()).padStart(2, '0');

        const paramData = props.prop_search;

        searchParam.theme_code = paramData.theme_code;
        searchParam.date = paramData.ymd;
        if (searchParam.date == '') {
            searchParam.date = `${yyyy}-${mm}-${dd}`;
        }
        await getThemeList(searchParam.date);
        await getThemeDetailList();
    }

    onMounted(fetchMenu);
    
    watch(() => [props.prop_search.ymd, props.prop_search.theme_code], fetchMenu)


    /**
     * vue functions
     */
    const getThemeList = async (ymdData) => {  

        const param = {
            'ymd': ymdData.replaceAll('-', '')
        }
        const { data } = await aibeesApi.get('/api/v1/themes/combo', { params: param });

        theme_list.value = data.data;
    }

    const getThemeDetailList = async () => {
        if (searchParam.theme_code == '' || searchParam.theme_code == undefined) {
            return false;
        }

        const param = {
            'ymd': searchParam.date.replaceAll('-', '')
        }

        const { data } = await aibeesApi.get('/api/v1/themes/' + searchParam.theme_code, { params: param })
        detail_list.value = data.data;
        
        detail_list.value.forEach(d => {
            d.per_rate = Number(d.per_rate).toFixed(2)
            d.curr_price = d.curr_price.toLocaleString();
            d.volume = d.volume.toLocaleString();
        })
    }
</script>

<style lang="scss" src="@@/stocks/Detail-List-Mobile.scss" scoped></style>

