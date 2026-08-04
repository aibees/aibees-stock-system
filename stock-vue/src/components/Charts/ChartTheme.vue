<template>
    <div id="charts-theme">
        <Headers :prop_title=title />
        <div class="contents">
            <div class="body-mobile" v-if="isMobile">
                <ListMobile />
            </div>
            <div class="body-web" v-else>
                <ListWeb />
            </div>
        </div>
    </div>
</template>

<script setup>
    import ListMobile from './chartThemeTemplate/List-Mobile.vue'
    import ListWeb from './chartThemeTemplate/List-Web.vue'
    
    const isMobile = ref(window.innerWidth < 2100)
    const title = 'CHART THEME'

    const handleResize = () => {
        isMobile.value = window.innerWidth < 2100
    }

    onMounted(() => {
        window.addEventListener('resize', handleResize)
    })

    onUnmounted(() => {
        window.removeEventListener('resize', handleResize)
    })

</script>
<style src="@@/charts/ChartTheme.css" scoped>

#charts-theme {
    width: 100%;
    height: 100vh;
    margin: auto;
    background-color: #212121;
}
</style>