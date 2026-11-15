<template>
  <canvas ref="canvasRef"></canvas>
  <!-- <canvas ref="canvas2Ref" style="height: 150px"></canvas> -->
</template>

<script setup>
import { ref, watch, onMounted, computed } from 'vue'
import { Chart, registerables } from 'chart.js'
import { CandlestickController, CandlestickElement } from 'chartjs-chart-financial'
import 'chartjs-adapter-luxon'
import 'chartjs-plugin-zoom'
Chart.register(...registerables, CandlestickController, CandlestickElement)

const props = defineProps({
  chartData:    Object,
  extraOptions: Object,   // 호출 측에서 축·플러그인 오버라이드 전달
})

const canvasRef = ref(null)
let chartInstance = null

const baseOptions = {
  responsive: true,
  maintainAspectRatio: false,
  scales: {
    x: { type: 'category' },
    y: { position: 'left', beginAtZero: false },
  },
  plugins: {
    legend: {
      position: 'top',
      labels: { boxWidth: 20, padding: 15 },
    },
    zoom: {
      pan:  { enabled: true, mode: 'xy' },
      zoom: { wheel: { enabled: true }, pinch: { enabled: true }, mode: 'xy' },
    },
    tooltip: {
      callbacks: {
        label(context) {
          const l = context.dataset.label;
          if (l === 'Volume') {
            return `거래량: ${Number(context.parsed.y).toLocaleString()}`
          }
          const maMap = { MA5:'5일선', MA20:'20일선', MA60:'60일선', MA120:'120일선' };
          if (maMap[l]) return `${maMap[l]} : ${context.formattedValue}`;
          if (l === 'Candle') {
            const v = context.formattedValue.split(' ');
            const lines = ['시가:'+v[1], '고가:'+v[4], '저가:'+v[7], '종가:'+v[10]];
            if (context.raw?.rate != null) lines.push('변동률:' + context.raw.rate['y']);
            return lines;
          }
        }
      }
    }
  }
}

const mergedOptions = computed(() => {
  if (!props.extraOptions) return baseOptions;
  return {
    ...baseOptions,
    scales:  { ...baseOptions.scales,  ...(props.extraOptions.scales  || {}) },
    plugins: { ...baseOptions.plugins, ...(props.extraOptions.plugins || {}) },
  };
});

const renderChart = () => {
  if (chartInstance) chartInstance.destroy();
  chartInstance = new Chart(canvasRef.value.getContext('2d'), {
    type: 'candlestick',
    data: props.chartData,
    options: mergedOptions.value,
  });
}

onMounted(() => {
  renderChart()
})

watch(() => props.chartData, () => { renderChart() }, { deep: true })
</script>