<template>
    <div id="stock-detail">
        <Headers :prop_title=title />
        <div class="contents">
            <div class="body-mobile" v-if="isMobile">
                <ListMobile :prop_search="search_param" />
            </div>
            <div class="body-web" v-else>
                <ListWeb />
            </div>
        </div>

    </div>
</template>

<script setup>
    import ListMobile from './stockDetailTemplate/Detail-List-Mobile.vue'
    import ListWeb from './stockDetailTemplate/List-Web.vue'
    const isMobile = ref(window.innerWidth < 2100)
    const title = 'STOCK DETAIL'

    const route = useRoute()
    const search_param = reactive({
        'theme_code': '',
        'ymd': ''
    })

    const handleResize = () => {
        isMobile.value = window.innerWidth < 2100
    }

    onMounted(() => {
        window.addEventListener('resize', handleResize)
        search_param.theme_code = route.query.theme_code || ''
        search_param.ymd = route.query.ymd || ''
    })

    onUnmounted(() => {
        window.removeEventListener('resize', handleResize)
    })

</script>
<style src="@@/stocks/StockThemeDetail.css" scoped>

</style>