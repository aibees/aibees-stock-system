<template>
    <div :class="setButtonClass()">
        <slot />
    </div>
</template>

<script setup>

    const props = defineProps({
        type: String
    });

    const setButtonClass = () => {
        let classStr = 'custom-button-div';

        if (props.type == 'save') {
            return classStr.concat(' save');
        }

        if (props.type == 'delete') {
            return classStr.concat(' save');
        }

        return classStr.concat(' outline');
    }
</script>

<style lang="scss" scoped>
.custom-button-div {
    min-width: 60px;
    color: var(--sc-strong-text);
    padding: 0.6rem 1rem;
    border: none;
    border-radius: 0;
    font-size: 15px;
    cursor: pointer;
    transition: background-color 0.2s;
}

.outline {
    border: 2px solid var(--sc-border-strong);

    &:hover {
        background-color: var(--sc-strong-bg);
    }
}

.save {
    background-color: var(--sc-strong-bg);

    &:hover {
        background-color: var(--sc-strong-bg);
    }
}

.delete {

}
</style>