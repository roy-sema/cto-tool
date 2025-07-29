<script setup lang="ts">
const props = defineProps<{
  text: string;
}>();
</script>

<template>
  <button class="inline-block cursor-pointer text-blue hover:text-violet dark:hover:text-lightgrey">
    {{ props.text }}
  </button>
</template>
