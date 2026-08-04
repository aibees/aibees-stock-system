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
    color: #fafafa;
    padding: 0.6rem 1rem;
    border: none;
    border-radius: 10px;
    font-size: 15px;
    cursor: pointer;
    transition: background-color 0.2s;
}

.outline {
    border: 2px solid #cbcbcb;

    &:hover {
        background-color: #4b4b4b;
    }
}

.save {
    background-color: #2db400;

    &:hover {
        background-color: #2c9409;
    }
}

.delete {

}
</style>