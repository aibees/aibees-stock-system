<template>
    <canvas ref="canvasRef"></canvas>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { Chart, registerables } from 'chart.js'
Chart.register(...registerables)

const props = defineProps({
    points: { type: Array, default: () => [] }, // [{date, value}]
    color: { type: String, default: '#141414' },
})

const canvasRef = ref(null)
let chartInstance = null

const chartData = computed(() => ({
    labels: props.points.map(p => p.date),
    datasets: [{
        data: props.points.map(p => p.value),
        borderColor: props.color,
        backgroundColor: props.color + '1a',
        borderWidth: 1.5,
        pointRadius: 0,
        pointHoverRadius: 3,
        fill: true,
        tension: 0.2,
    }],
}))

const options = {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    interaction: { intersect: false, mode: 'index' },
    scales: {
        x: { display: false },
        y: { display: false },
    },
    plugins: {
        legend: { display: false },
        tooltip: {
            displayColors: false,
            callbacks: {
                title: (items) => items[0]?.label ?? '',
                label: (item) => `${item.formattedValue}%`,
            },
        },
    },
}

const renderChart = () => {
    if (!canvasRef.value) return
    if (chartInstance) chartInstance.destroy()
    chartInstance = new Chart(canvasRef.value.getContext('2d'), {
        type: 'line',
        data: chartData.value,
        options,
    })
}

onMounted(renderChart)
watch(() => props.points, renderChart, { deep: true })
onBeforeUnmount(() => { if (chartInstance) chartInstance.destroy() })
</script>
