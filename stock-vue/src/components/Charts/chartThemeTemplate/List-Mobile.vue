<template>
    <div id="chart-theme-mobile">
        <div class="search-div">
            <div class="div-flex search-item">
                <div class="code">
                    <SLabelInput 
                        id="search-code"
                        label="테마코드"
                        width="50px"
                        type="text"
                        align="center"
                        v-model="searchParam.theme_code"
                    />
                </div>
                <div class="name">
                    <!-- <SLabelInput 
                        id="search-name"
                        label="테마명"
                        width="110px"
                        type="text"
                        v-model="searchParam.theme_name"
                    /> -->
                    <select 
                        class="theme_select"
                        v-model="searchParam.theme_code">
                        <option v-for="th in theme_list" :key="th.theme_code" :value="th.theme_code">
                            {{ th.theme_name }}
                        </option>
                    </select>
                </div>
            </div>
            <div class="div-flex search-item">
                <div class="date">
                    <SLabelInput 
                        id="search-date"
                        label="일자"
                        type="date"
                        width="100px"
                        v-model="searchParam.date"
                        @change="getThemeList(searchParam.date)"
                    />
                </div>
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
            <button @click="getChartThemeData">
                <font-awesome-icons :icon="['fa-solid', 'fa-magnifying-glass']" />
            </button>
        </div>
        <div class="chart-div">
            <div class="chart-item" :style="{ width: dynamicChartWidth }">
                <Line ref="chartRef" :data="chartResultdata" :options="chartOptions" />
            </div>
        </div>
        
    </div>
</template>

<script setup>
    import { onMounted, reactive, ref, computed } from 'vue';
    import SLabelInput from '../../common/comp/SLabelInput.vue'
    import aibeesApi from '../../../scripts/aibeesApi.js'
    import { Line } from 'vue-chartjs';
    import {
        Chart as ChartJS,
        Title,
        Tooltip,
        Legend,
        LineElement,
        CategoryScale,
        Filler,
        LinearScale,
        PointElement
    } from 'chart.js'

    ChartJS.register(Title, Tooltip, Legend, Filler, LineElement, CategoryScale, LinearScale, PointElement)
    
    const chartRef = ref()
    const labelData = ref([]);
    const todayData = ref([]);
    const threeData = ref([]);

    let chartResultdata = computed(() => ({
        labels: labelData.value,
        datasets: [{
            label: '일별 증감률 (%)',
            data: todayData.value,
            tension: 0.4,
            fill: true,
            pointRadius: 2,
            borderWidth: 2,
            backgroundColor: 'rgba(75, 192, 192, 0.5)',
        }, {
            label: '3일 평균 증감률 (%)',
            data: threeData.value,
            tension: 0.4,
            fill: true,
            pointRadius: 2,
            borderWidth: 2,
            backgroundColor: 'rgba(75, 1, 192, 0.5)',
        }]
    }));

    const chartOptions = reactive({
        responsive: true,
        maintainAspectRatio: false,
        scales: {
            y: {
            title: {
                text: '변동률 (%)'
            },
            ticks: {
                callback: value => `${value}%`
            }
            },
            x: {
            title: {
                display: true,
                text: '날짜'
            }
            }
        },
        plugins: {
            tooltip: {
            callbacks: {
                label: (context) => `변동률: ${context.parsed.y}%`
            }
            }
        }
    });

    const theme_list = ref([]);
    const searchParam = reactive({
        theme_code: '',
        theme_name: '',
        date: '',
        limit: 30
    });

    onMounted(() => {
        const today = new Date();
        const yyyy = today.getFullYear();
        const mm = String(today.getMonth() + 1).padStart(2, '0'); // 월: 0부터 시작하므로 +1
        const dd = String(today.getDate()).padStart(2, '0');

        searchParam.date = `${yyyy}-${mm}-${dd}`;
        getThemeList(searchParam.date);
    });

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

    const getChartThemeData = async () => {
        const param = {
            'ymd': searchParam.date.replaceAll('-', ''),
            'theme_code': searchParam.theme_code,
            'limits': searchParam.limit
        }

        const { data } = await aibeesApi.get('/api/v1/charts/themes', { params: param });
        const resultData = data.data;
        labelData.value = resultData.label;
        todayData.value = resultData.perToday;
        threeData.value = resultData.perThree;
    }

    const dynamicChartWidth = computed(() => {
        const minPerLabel = 60  // px per label
        const labelCount = labelData.value.length
        return Math.max(labelCount * minPerLabel, 400) + 'px'
    })
</script>

<style lang="scss" scoped>
@use '@@/common.scss' as *;

.theme_select {
    width: 170px;
    border: 1px solid rgb(102, 102, 102);
}

#chart-theme-mobile {
    .search-div {
        font-size: 12px;
        width: 95%;
        height: 57px;
        margin: 5px auto;
        border-radius: 7px;
        background-color: #353535;
        margin-top : 100px;

        .search-item {
            margin: auto;
            padding: 5px 10px;
        }
    }

    .buttons-div {
        margin: 7px 4px 6px 4px;
        text-align: right;
    }

    .chart-div {
        width: 100%;
        overflow: scroll;
        background-color: white;

        .chart-item {
            width: 200%;
            height: 300px;
        }
    }
}
</style>