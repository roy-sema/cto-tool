<script setup lang="ts">
import { ChevronDoubleRightIcon } from "@heroicons/vue/24/outline";
import { computed } from "vue";

const props = defineProps<{
  exclude?: string;
}>();

const links = [
  {
    label: "See Executive Summary",
    to: "executive-summary",
  },
  {
    label: "See Product Detail",
    to: "product-detail",
  },
  {
    label: "See Compliance Detail",
    to: "compliance-detail",
  },
];

const buttons = computed(() => {
  return links.filter((link) => link.to !== props.exclude);
});
</script>

<template>
  <div class="pb-10">
    <Divider class="!my-10" />

    <div class="flex flex-col gap-3 sm:w-64">
      <Button
        v-for="button in buttons"
        :key="button.to"
        as="router-link"
        :to="{ name: button.to }"
        iconPos="right"
        severity="secondary"
        size="small"
        variant="outlined"
      >
        <div class="flex w-full items-center justify-between">
          {{ button.label }}
          <ChevronDoubleRightIcon class="size-4" />
        </div>
      </Button>
    </div>
  </div>
</template>
