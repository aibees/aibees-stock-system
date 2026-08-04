<template>
    <div class="search-item">
        <slot />
    </div>
</template>

<script setup>

</script>

<style lang="scss" scoped>
.search-item {
    // flex: 1;
    min-width: 180px;

    input,
    select {
        width: 100%;
        padding: 0.4rem 0.6rem;
        border-radius: 6px;
        font-size: 14px;
        color: white;
        background-color: transparent;
        transition: border-color 0.2s;

        &:focus {
            border-color: #2db400;
            outline: none;
            box-shadow: 0 0 5px rgba(56, 99, 17, 0.3);
        }
    }
}
</style>