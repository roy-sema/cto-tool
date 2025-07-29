<script setup lang="ts">
import { XMarkIcon } from "@heroicons/vue/24/outline";
import { computed, ref } from "vue";

const props = defineProps<{
  info?: boolean;
  success?: boolean;
  warning?: boolean;
  error?: boolean;
  dismissable?: boolean;
}>();

const visible = ref(true);

const colorClassMap: Record<string, string> = {
  info: "bg-sky-100 border-sky-400 text-sky-700",
  success: "bg-green-100 border-green-400 text-green-700",
  warning: "bg-yellow-100 border-yellow-400 text-yellow-700",
  error: "bg-red-100 border-red-400 text-red-700",
};

const colorClass = computed(() => {
  for (const key in colorClassMap) {
    if ((props as Record<string, boolean>)[key]) return colorClassMap[key];
  }
  return "";
});
</script>

<template>
  <div
    v-if="visible"
    :class="colorClass"
    class="relative rounded border px-4 py-3 text-sm"
    :role="props.info ? 'status' : 'alert'"
  >
    <div class="flex items-center justify-between gap-3">
      <div>
        <slot></slot>
      </div>
      <XMarkIcon v-if="props.dismissable" class="size-4 cursor-pointer" @click="visible = false" />
    </div>
  </div>
</template>
