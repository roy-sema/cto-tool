<script setup lang="ts">
import { computed, ref } from "vue";

const props = withDefaults(
  defineProps<{
    value: number;
    valueLabel: string;
    valueSecondary?: number;
    valueSecondaryLabel?: string;
    showValues?: boolean;
    color?: "red" | "orange" | "yellow" | "green" | "blue";
  }>(),
  {
    showValues: true,
    color: "blue",
  },
);

const widthValue = computed(() => `${props.value}%`);
const widthValueSecondary = computed(() => `${props.valueSecondary}%`);
const isHoveredPrimary = ref(false);
const isHoveredSecondary = ref(false);

const notOnEdge = (_value: number) => _value > 5 && _value < 95;
</script>

<template>
  <div :class="{ 'pb-3': showValues }">
    <div
      role="progressbar"
      :class="`p-progressbar p-component p-progressbar-determinate !h-1.5 progress-${color}`"
      aria-valuemin="0"
      :aria-valuenow="value"
      aria-valuemax="100"
    >
      <!-- this is a hack to make the progress bar work otherwise the css is not applied -->
      <ProgressBar class="!hidden" />
      <div
        v-if="valueSecondary"
        class="p-progressbar-value p-progressbar-value-striped flex"
        :style="`width: ${widthValueSecondary};`"
        @mouseenter="isHoveredSecondary = true"
        @mouseleave="isHoveredSecondary = false"
      ></div>
      <div
        class="p-progressbar-value z-10 flex"
        :style="`width: ${widthValue};`"
        @mouseenter="isHoveredPrimary = true"
        @mouseleave="isHoveredPrimary = false"
      ></div>
    </div>
    <div v-if="showValues" class="relative w-full">
      <div
        class="absolute rounded-md px-1.5"
        :class="{
          '-translate-x-1/2': notOnEdge(value),
          'is-other-hovered': isHoveredSecondary,
          'is-hovered': isHoveredPrimary,
          [`is-hovered-${color}`]: color,
        }"
        :style="value < 5 ? 'left: 0' : `left: ${value}%`"
      >
        <span class="text-xs">{{ valueLabel }}</span>
      </div>
      <div
        v-if="valueSecondary"
        class="absolute rounded-md px-1.5"
        :class="{
          '-translate-x-1/2': notOnEdge(valueSecondary),
          'is-other-hovered': isHoveredPrimary,
          'is-hovered': isHoveredSecondary,
          [`is-hovered-${color}`]: color,
        }"
        :style="valueSecondary > 95 ? 'right: 0' : `left: ${valueSecondary}%`"
      >
        <span class="whitespace-nowrap text-xs">{{ valueSecondaryLabel }}</span>
      </div>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.p-progressbar-value-striped {
  background-image: linear-gradient(
    135deg,
    rgba(255, 255, 255, 0.75) 25%,
    rgba(255, 255, 255, 0.1) 25%,
    rgba(255, 255, 255, 0.1) 50%,
    rgba(255, 255, 255, 0.75) 50%,
    rgba(255, 255, 255, 0.75) 75%,
    rgba(255, 255, 255, 0.1) 75%
  ) !important;
  background-size: 10px 10px !important;
}

.p-progressbar-value:hover {
  filter: brightness(1.5) saturate(1.5);
}

.is-hovered {
  @apply z-30;

  &.is-hovered-red {
    @apply bg-red-100 dark:bg-red-800;
  }

  &.is-hovered-orange {
    @apply bg-orange-100 dark:bg-orange-900;
  }

  &.is-hovered-yellow {
    @apply bg-amber-100 dark:bg-amber-900;
  }

  &.is-hovered-green {
    @apply bg-green-100 dark:bg-green-800;
  }

  &.is-hovered-blue {
    @apply bg-sky-100 dark:bg-sky-900;
  }
}

.is-other-hovered {
  @apply opacity-30;
}
</style>
