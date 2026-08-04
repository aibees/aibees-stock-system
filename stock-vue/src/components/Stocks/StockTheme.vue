<template>
    <div id="stock-theme">
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
    import ListMobile from './stockThemeTemplate/Theme-List-Mobile.vue'
    import ListWeb from './stockThemeTemplate/List-Web.vue'
    
    const isMobile = ref(window.innerWidth < 2100)
    const title = '네이버 증권 테마'

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
<style src="@@/stocks/StockTheme.css" scoped>

</style>
