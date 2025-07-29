<script setup lang="ts">
import Datepicker from "@vuepic/vue-datepicker";
import "@vuepic/vue-datepicker/dist/main.css";
import { subDays } from "date-fns";
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";

interface PresetDate {
  label: string;
  value: [Date, Date];
  slot: string;
}

const props = withDefaults(
  defineProps<{
    date: [Date, Date] | null;
    position?: () => { top: number; left: string };
    firstDate?: string;
  }>(),
  {
    position: () => ({ top: 44, left: "auto" }),
  },
);

defineEmits(["update:date"]);

let modelDate = ref<[Date, Date] | null>(null);
modelDate.value = props.date;

watch(
  () => props.date,
  (newVal) => {
    modelDate.value = newVal;
  },
  { immediate: true, deep: true },
);

// TODO: when the theme dropdown is done with Vue, we can use centralized storage instead
const isDarkMode = () => {
  return document.documentElement.classList.contains("dark");
};

const isDark = ref<boolean>(isDarkMode());
const observer = new MutationObserver(() => {
  isDark.value = isDarkMode();
});

const today = new Date();
const minDate = computed(() => {
  if (props.firstDate) return new Date(props.firstDate);
  return new Date("2020-01-01");
});

const boundMinDate = (date: Date) => new Date(Math.max(minDate.value.getTime(), date.getTime()));

const presetDates = ref<PresetDate[]>([
  {
    label: "Last 7 days",
    value: [boundMinDate(subDays(today, 6)), today],
    slot: "preset-date-range-button",
  },
  {
    label: "Last 14 days",
    value: [boundMinDate(subDays(today, 13)), today],
    slot: "preset-date-range-button",
  },
  {
    label: "Last 30 days",
    value: [boundMinDate(subDays(today, 29)), today],
    slot: "preset-date-range-button",
  },
  {
    label: "Last 90 days",
    value: [boundMinDate(subDays(today, 89)), today],
    slot: "preset-date-range-button",
  },
  {
    label: "Last 365 days",
    value: [boundMinDate(subDays(today, 364)), today],
    slot: "preset-date-range-button",
  },
  {
    label: "All time",
    value: [minDate.value, today],
    slot: "preset-date-range-button",
  },
]);

onMounted(() => {
  observer.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["class"],
  });
});

onBeforeUnmount(() => {
  observer.disconnect();
});
</script>

<template>
  <Datepicker
    v-model="modelDate"
    class="mt-3 w-52 md:mt-0"
    :alt-position="position"
    :clearable="false"
    :dark="isDark"
    :enable-time-picker="false"
    :preset-dates="presetDates"
    :max-date="today"
    :min-date="minDate"
    utc="preserve"
    range
    multi-calendars
    position="right"
    @update:model-value="$emit('update:date', $event)"
  >
    <template #preset-date-range-button="{ label, value, presetDate }">
      <button
        class="dp__btn dp--preset-range"
        @click="presetDate(value)"
        @keyup.enter.prevent="presetDate(value)"
        @keyup.space.prevent="presetDate(value)"
      >
        {{ label }}
      </button>
    </template>
  </Datepicker>
</template>

<style>
.dp__main {
  width: 15rem;
}
.dp__input {
  --dp-background-color: transparent;
  @apply border-lightgrey text-base dark:border-slate-600 sm:text-sm;
}
/* Fix positioning */
.dp__outer_menu_wrap {
  left: 0;
}
@media (min-width: 768px) {
  .dp__outer_menu_wrap {
    left: auto;
    right: 0;
  }
}

:root {
  --dp-font-size: 0.85rem;
  --dp-cell-size: 2rem;
  --dp-action-button-height: 1.5rem;
  --dp-action-buttons-padding: 0.25rem 0.75rem;
}
.dp__theme_light {
  --dp-primary-color: theme("colors.blue");
}
.dp__theme_dark {
  --dp-background-color: theme("colors.slate.900");
  --dp-hover-color: theme("colors.slate.600");
  --dp-primary-color: theme("colors.blue");
  --dp-border-color: theme("colors.slate.600");
  --dp-menu-border-color: theme("colors.slate.600");
}
</style>
