<script setup lang="ts">
import { computed } from "vue";

interface Option {
  [key: string]: any;
}

type SelectSize = "small" | "large";

const props = defineProps({
  modelValue: { type: Array as () => any[], default: () => [] },
  options: { type: Array as () => Option[], required: true },
  optionLabel: { type: String, default: "name" },
  optionValue: { type: String, default: "id" },
  placeholder: { type: String, default: "" },
  maxSelectedLabels: { type: Number, default: 3 },
  showToggleAll: { type: Boolean, default: false },
  containerClass: { type: String, default: "w-full md:w-80" },
  size: { type: String as () => SelectSize, default: "small" },
});

const emit = defineEmits<{
  (e: "update:modelValue", value: any[]): void;
  (e: "change", event: any): void;
}>();

// Create an internal copy of the selected values
const internalSelected = computed({
  get: () => props.modelValue,
  set: (value) => emit("update:modelValue", value),
});

const updateSelection = (newValue: any[]) => {
  emit("update:modelValue", newValue);
  emit("change", newValue);
};

const clearSelection = () => updateSelection([]);
const selectOnly = (selection: Option) => updateSelection([selection[props.optionValue]]);
const selectAll = () => updateSelection(props.options.map((item) => item[props.optionValue]));
</script>

<template>
  <MultiSelect
    v-model="internalSelected"
    :options="options"
    :optionLabel="optionLabel"
    :optionValue="optionValue"
    :placeholder="placeholder"
    :maxSelectedLabels="maxSelectedLabels"
    :showToggleAll="showToggleAll"
    :class="containerClass"
    :size="size"
    class="max-w-full"
    @change="emit('change', $event)"
  >
    <template #option="slotProps">
      <div class="flex w-full items-center justify-between">
        <div class="max-w-96 truncate text-sm md:max-w-56">{{ slotProps.option[optionLabel] }}</div>
        <div class="text-xs text-blue" @click.stop="selectOnly(slotProps.option)">only</div>
      </div>
    </template>
    <template #footer>
      <div class="compass flex justify-between p-4 text-xs text-blue">
        <div class="cursor-pointer" @click="selectAll">Select all</div>
        <div
          class="cursor-pointer"
          :class="{ 'cursor-default text-gray-300 dark:text-gray-600': !internalSelected?.length }"
          @click="clearSelection"
        >
          Clear selection
        </div>
      </div>
    </template>
  </MultiSelect>
</template>
