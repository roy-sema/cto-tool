<script setup lang="ts">
import TWESpinner from "@/aicm/components/common/TWESpinner.vue";
import { colors } from "@/common/apexcharts/config";
import type { ApexOptions } from "apexcharts";
import { cloneDeep } from "lodash";
import { computed, onMounted, ref } from "vue";
import { default as ApexChart } from "vue3-apexcharts";

const props = withDefaults(
  defineProps<{
    id: string;
    title: string;
    data: any;
    maxY?: number | null;
    height?: number;
    loading?: boolean;
    tooltipSuffix?: string;
  }>(),
  {
    height: 150,
    tooltipSuffix: "%",
  },
);

const defaultOptions: ApexOptions = {
  chart: {
    type: "line",
    stacked: true,
    fontFamily: "Inter, sans-serif",
    redrawOnParentResize: true,
    toolbar: { show: false },
    zoom: { enabled: false },
    width: "100%",
  },
  colors: colors,
  dataLabels: { enabled: false },
  xaxis: { type: "datetime" },
  yaxis: { decimalsInFloat: 0 },
  tooltip: {
    x: { format: "dd MMM" },
    y: { formatter: (value: number) => `${value}${props.tooltipSuffix}` },
  },
  legend: {
    position: "bottom",
    offsetY: 5,
  },
  fill: { opacity: 1 },
};

const ready = ref(false);

const series = computed(() => props.data?.series || []);

const chartOptions = computed(() => {
  const options = cloneDeep(defaultOptions);

  (options.chart as ApexChart).id = props.id;
  (options.xaxis as ApexXAxis).categories = props.data.categories;
  if (props.maxY) {
    (options.yaxis as ApexYAxis).max = props.maxY;
  }

  return options;
});

onMounted(() => {
  // fix resizing issue
  setTimeout(() => (ready.value = true), 0);
});
</script>

<template>
  <div class="chart-container mb-2">
    <div class="mb-3 flex items-center justify-between">
      <h4 class="font-semibold">{{ title }}</h4>
      <TWESpinner v-if="loading" :size="4" class="mr-1 opacity-80" />
    </div>
    <div class="relative rounded-md border border-gray-200 bg-white dark:border-slate-600 dark:bg-slate-900">
      <ApexChart v-if="ready" :options="chartOptions" :series="series" :height="height" />
      <div v-else-if="!series" class="relative">
        <div class="z-2 absolute inset-0 flex items-center justify-center rounded-xl bg-black bg-opacity-30 p-5">
          <p class="transform text-center text-xl font-bold text-white md:text-2xl">No data available yet.</p>
        </div>
      </div>
    </div>
  </div>
</template>
