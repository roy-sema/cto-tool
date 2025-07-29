<script setup lang="ts">
import { computed } from "vue";

const props = defineProps({
  progress: { type: Number, required: true },
  max: { type: Number, required: true },
  progressColor: { type: String, default: "bg-blue" },
  content: { type: String },
});

const percentage = computed(() => (props.progress / props.max) * 100);
const height = computed(() => (props.content ? "h-6" : "h-2.5"));
</script>

<template>
  <div :class="`w-full overflow-clip rounded bg-neutral-200 dark:bg-slate-600 ${height}`">
    <div
      class="h-full content-center text-center text-xs font-medium leading-none text-primary-100"
      :class="progressColor"
      :style="{ width: percentage + '%' }"
    >
      <div v-if="content" class="p-0.5">
        {{ content }}
      </div>
    </div>
  </div>
</template>
