<script setup lang="ts">
import { round } from "@/aicm/helpers/utils";
import { colors as apexColors } from "@/common/apexcharts/config";
import type { ApexOptions } from "apexcharts";
import { cloneDeep, snakeCase } from "lodash";
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { default as ApexChart } from "vue3-apexcharts";

const props = withDefaults(
  defineProps<{
    id: string;
    data: any;
    colors?: string[];
    height?: number;
    loading?: boolean;
    title?: string;
    tooltipSuffix?: string;
  }>(),
  {
    height: 350,
    tooltipSuffix: "%",
  },
);

const defaultOptions: ApexOptions = {
  chart: {
    type: "bar",
    stacked: true,
    fontFamily: "Inter, sans-serif",
    redrawOnParentResize: true,
    toolbar: {
      show: true,
      export: {
        csv: {
          filename: snakeCase(props.title),
          headerCategory: "Date",
        },
      },
    },
    zoom: { enabled: false },
    width: "100%",
  },
  plotOptions: {
    bar: { horizontal: true },
  },
  colors: apexColors,
  dataLabels: { enabled: false },
  grid: {
    strokeDashArray: 2,
    xaxis: {
      lines: { show: true },
    },
    yaxis: {
      lines: { show: false },
    },
  },
  xaxis: { min: 0, max: 100, stepSize: 25 },
  yaxis: {
    // Position the y-axis labels to align annotations
    floating: true,
    labels: {
      align: "left",
      offsetX: 10,
      offsetY: 1,
      show: true,
      style: {
        colors: ["transparent"],
      },
    },
    showAlways: true,
  },
  tooltip: {
    x: { format: "dd MMM" },
    y: { formatter: (value: number) => `${round(value)}${props.tooltipSuffix}` },
  },
  legend: {
    position: "top",
    offsetY: 5,
  },
  fill: { opacity: 1 },
};

const ready = ref(false);

const series = computed(() => props.data?.series || []);

const chartOptions = computed(() => {
  const options = cloneDeep(defaultOptions);

  if (!props.data.categories) {
    return options;
  }

  (options.chart as ApexChart).id = props.id;
  (options.xaxis as ApexXAxis).categories = props.data.categories;

  // Using annotations because they have more styling options than labels
  options.annotations = {
    yaxis: props.data.categories.map((category: string) => ({
      y: category,
      y2: category,
      label: {
        borderColor: "transparent",
        offsetX: 15,
        offsetY: 3,
        position: "left",
        style: {
          fontWeight: 700,
        },
        text: category,
        textAnchor: "start",
      },
    })),
  };

  if (props.colors) {
    options.colors = props.colors;
  }

  return options;
});

// Fix bug when filtering categories
watch(
  () => props.data,
  () => {
    ready.value = false;
    nextTick(() => (ready.value = true));
  },
);

onMounted(() => {
  // fix resizing issue
  setTimeout(() => (ready.value = true), 0);
});
</script>

<template>
  <div class="chart-container mb-2">
    <div class="chart-header mb-3 flex items-center justify-between">
      <h4 class="font-semibold">{{ title }}</h4>
      <div class="chart-spinner-container mr-1">
        <ProgressSpinner v-if="loading" class="!size-5" />
      </div>
    </div>
    <!-- Set height to prevent resize issues due to vertical scroll change -->
    <div class="relative" :style="`min-height: ${height}px;`">
      <ApexChart v-if="ready" :options="chartOptions" :series="series" :height="height" />
      <div
        v-if="data.no_data || !series"
        class="z-2 absolute inset-0 flex items-center justify-center rounded-xl bg-black bg-opacity-30 p-5"
      >
        <p class="transform text-center text-xl font-bold text-white md:text-2xl">
          {{ data.no_data ? "No data reported" : "No data available yet." }}
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
:deep(.apexcharts-legend) {
  @apply mx-10;
}
</style>
