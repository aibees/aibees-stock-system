<template>
    <div id="chart-stock-web">
        <div class="search-div">
            <div class="search-item">
                <div class="code">
                    <SAutoInput 
                        id="search-code"
                        label="종목"
                        width="100px"
                        type="text"
                        align="center"
                        v-model:code="searchParam.search.code"
                        v-model:name="searchParam.search.name"
                    />
                </div>
            </div>
            <div class="search-item">
                <div class="limits">
                    <SLabelInput 
                        id="search-limit"
                        label="Limit"
                        width="50px"
                        type="text"
                        align="center"
                        v-model="searchParam.limit"
                    />
                </div>
            </div>
        </div>
        <div class="buttons-div">
            <button @click="getStockChartData">
                <font-awesome-icons :icon="['fa-solid', 'fa-magnifying-glass']" />
            </button>
            <button @click="getStockChartData">
                <font-awesome-icons :icon="['fa-solid', 'fa-magnifying-glass']" />
            </button>
        </div>
    </div>
    <div id="chart-grid-web">
        <div class="chart-div">
            <div class="chart-item" :style="{ width: dynamicChartWidth, height: '66vh' }">
                <CandlestickChart :chartData="chartData" />
            </div>
        </div>
    </div>
</template>

<script setup>
    import { onMounted, reactive, ref, computed, vShow } from 'vue';
    import aibeesApi from '../../../scripts/aibeesApi.js'
    import { useRoute } from 'vue-router';
    import SAutoInput from '../../common/comp/SAutoInput.vue'
    import SLabelInput from '../../common/comp/SLabelInput.vue'
    import CandlestickChart from '../../common/comp/CandlestickChart.vue'

    const props = defineProps({ prop_search: Object });
    const searchParam = reactive({
        search: {
            code: '',
            name: ''
        },
        theme_name: '',
        date: '',
        limit: 60
    });

    const fetchMenu = async () => {
        const code = props.prop_search.stock_code;
        searchParam.search.code = code;

        if (code !== '') {
            await setStockInfo(code);
            await getStockChartData();
        }
    }

    onMounted(fetchMenu);

    // data ref
    const dateLabelData = ref([]);
    const candleData = ref([]);
    const ma005Data = ref([]);
    const ma020Data = ref([]);
    const ma060Data = ref([]);
    const ma120Data = ref([]);
    const volumeData = ref([]);

    let chartData = ref({
            datasets: [ 
                {   
                    label: 'Candle',
                    data: candleData.value,
                    color: {
                        up: '#00ff00',
                        down: '#ff0000',
                        unchanged: '#999999'
                    }
                }
                , {
                    label: 'ma5',
                    data: ma005Data.value, // line chart 데이터 (x, y 값)
                    borderColor: '#f38980',
                    type: 'line' // line 타입 설정
                }
                , {
                    label: 'ma20',
                    data: ma020Data.value, // line chart 데이터 (x, y 값)
                    borderColor: '#efa55b',
                    type: 'line' // line 타입 설정
                }
                , {
                    label: 'ma60',
                    data: ma060Data.value, // line chart 데이터 (x, y 값)
                    borderColor: '#d0fe48',
                    type: 'line' // line 타입 설정
                }
                , {
                    label: 'ma120',
                    data: ma120Data.value, // line chart 데이터 (x, y 값)
                    borderColor: '#01b6f3',
                    type: 'line' // line 타입 설정
                }
            ]
        }
    );

    const setStockInfo = async (code) => {
        const { data } = await aibeesApi.get("/api/v1/stocks/id/" + code);
        searchParam.search.code = data.data.stock_code;
        searchParam.search.name = data.data.stock_name;
    }

    /**
     * vue functions
     */
    const getStockChartData = async () => {
        chartData = ref(null);

        let code = searchParam.search.code || props.prop_search.code;

        const { data } = await aibeesApi.get('/api/v1/charts/stock/' + code)

        dateLabelData.value = data.data.date.Date;
        candleData.value = data.data.ohcl;

        candleData.value = candleData.value.slice((-1) * searchParam.limit)
        ma005Data.value = data.data.ma5.slice((-1) * searchParam.limit)
        ma020Data.value = data.data.ma20.slice((-1) * searchParam.limit)
        ma060Data.value = data.data.ma60.slice((-1) * searchParam.limit)
        ma120Data.value = data.data.ma120.slice((-1) * searchParam.limit)
        volumeData.value = data.data.volume.slice((-1) * searchParam.limit)

        chartData = ref({
            datasets: [ 
                {   
                    label: 'Candle',
                    data: candleData.value,
                    color: {
                        up: '#c51300',
                        down: '#03748d',
                        unchanged: '#999999'
                    }
                }
                , {
                    label: 'ma5',
                    data: ma005Data.value, // line chart 데이터 (x, y 값)
                    borderColor: '#f38980',
                    type: 'line' // line 타입 설정
                }
                , {
                    label: 'ma20',
                    data: ma020Data.value, // line chart 데이터 (x, y 값)
                    borderColor: '#efa55b',
                    type: 'line' // line 타입 설정
                }
                , {
                    label: 'ma60',
                    data: ma060Data.value, // line chart 데이터 (x, y 값)
                    borderColor: '#d0fe48',
                    type: 'line' // line 타입 설정
                }
                , {
                    label: 'ma120',
                    data: ma120Data.value, // line chart 데이터 (x, y 값)
                    borderColor: '#01b6f3',
                    type: 'line' // line 타입 설정
                }
                // , {
                //     label: 'volume',
                //     data: volumeData.value, // line chart 데이터 (x, y 값)
                //     borderColor: '#ac44fd',
                //     type: 'bar' // line 타입 설정
                // }
            ]
        });
    }

    const dynamicChartWidth = computed(() => {
        const minPerLabel = 30  // px per label
        const labelCount = dateLabelData.value.length
        return Math.max(labelCount * minPerLabel, 400) + 'px'
    })
</script>

<style lang="scss" src="@@/charts/Chart-Stock-Web.scss" scoped></style>

