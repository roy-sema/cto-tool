<script setup lang="ts">
import type { ApexOptions } from "apexcharts";
import { cloneDeep } from "lodash";
import { computed, onMounted, ref } from "vue";
import { default as ApexChart } from "vue3-apexcharts";

const props = withDefaults(
  defineProps<{
    id: string;
    title: string;
    data: any;
    height?: number;
    loading?: boolean;
  }>(),
  {
    height: 300,
  },
);

const blueColor = "#3B82F6";
const orangeColor = "#F97316";

const defaultOptions: ApexOptions = {
  chart: {
    type: "line",
    fontFamily: "Inter, sans-serif",
    redrawOnParentResize: true,
    toolbar: { show: false },
    zoom: { enabled: false },
    width: "100%",
  },
  colors: [blueColor],
  xaxis: {
    type: "datetime",
    labels: {
      format: "MMM dd",
    },
  },
  yaxis: {
    decimalsInFloat: 1,
    min: 0,
    max: 100,
    title: {
      text: "Average Completeness Score",
    },
  },
  tooltip: {
    enabled: true,
    followCursor: true,
    custom: function ({ series, seriesIndex, dataPointIndex, w }) {
      const data = w.globals.initialSeries[seriesIndex].data[dataPointIndex];
      const date = new Date(data.x);
      const formattedDate = date.toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
      });

      // Get data from the original results array
      const originalData = props.data?.results?.[dataPointIndex];
      const ticketCount = originalData?.ticket_count || 0;
      const completenessScore = originalData?.avg_completeness_score;
      const organizationalBenchmark = props.data?.organizational_benchmark;

      let tooltipContent = `<div class="apexcharts-tooltip-title">${formattedDate}</div>`;

      // Only show TCS if it's not null
      if (completenessScore !== null) {
        tooltipContent += `<div class="apexcharts-tooltip-y-group">`;
        tooltipContent += `<span class="apexcharts-tooltip-y-label">Average TCS:</span>`;
        tooltipContent += `<span class="apexcharts-tooltip-y-value">${completenessScore.toFixed(1)}</span>`;
        tooltipContent += `</div>`;
      } else {
        tooltipContent += `<div class="apexcharts-tooltip-y-group">`;
        tooltipContent += `<span class="apexcharts-tooltip-y-label">Average TCS:</span>`;
        tooltipContent += `<span class="apexcharts-tooltip-y-value">No data</span>`;
        tooltipContent += `</div>`;
      }

      tooltipContent += `<div class="apexcharts-tooltip-y-group">`;
      tooltipContent += `<span class="apexcharts-tooltip-y-label">Ticket Count:</span>`;
      tooltipContent += `<span class="apexcharts-tooltip-y-value">${ticketCount}</span>`;
      tooltipContent += `</div>`;

      // Add organizational benchmark if available
      if (organizationalBenchmark !== null) {
        tooltipContent += `<div class="apexcharts-tooltip-y-group">`;
        tooltipContent += `<span class="apexcharts-tooltip-y-label">Organizational Benchmark:</span>`;
        tooltipContent += `<span class="apexcharts-tooltip-y-value">${organizationalBenchmark.toFixed(1)}</span>`;
        tooltipContent += `</div>`;
      }

      return tooltipContent;
    },
  },
  grid: {
    strokeDashArray: 4,
    xaxis: {
      lines: { show: true },
    },
    yaxis: {
      lines: { show: true },
    },
  },
  fill: {
    opacity: 1,
  },
  noData: {
    text: "No data available",
    align: "center",
    verticalAlign: "middle",
    offsetX: 0,
    offsetY: 0,
    style: {
      color: "#64748b",
      fontSize: "14px",
      fontFamily: "Inter, sans-serif",
    },
  },
};

const ready = ref(false);

const series = computed(() => {
  if (!props.data?.results) return [];

  // Include all data points, but use null for Y values when completeness score is null
  const allData = props.data.results;

  const series = [
    {
      name: "Average Completeness Score",
      data: allData.map((item: any) => ({
        x: new Date(item.date).getTime(),
        y: item.avg_completeness_score, // This will be null for missing data
      })),
    },
  ];

  // Add organizational benchmark line if available
  if (props.data.organizational_benchmark !== null && allData.length > 0) {
    const benchmarkData = allData.map((item: any) => ({
      x: new Date(item.date).getTime(),
      y: props.data.organizational_benchmark,
    }));

    series.push({
      name: "Organizational Benchmark",
      data: benchmarkData,
    });
  }

  return series;
});

const chartOptions = computed(() => {
  const options = cloneDeep(defaultOptions);
  (options.chart as any).id = props.id;

  // Update colors to include orange for benchmark line
  if (props.data?.organizational_benchmark !== null) {
    options.colors = [blueColor, orangeColor]; // Blue for main line, orange for benchmark
  } else {
    options.colors = [blueColor]; // Only blue for main line
  }

  // Update stroke styles to include dashed line for benchmark
  if (props.data?.organizational_benchmark !== null) {
    options.stroke = {
      curve: "smooth",
      width: [3, 2], // Main line 3px, benchmark line 2px
      dashArray: [0, 5], // Solid for main line, dashed for benchmark
    };
  } else {
    options.stroke = {
      curve: "smooth",
      width: 3,
    };
  }

  // Update markers to only show for main line
  if (props.data?.organizational_benchmark !== null) {
    options.markers = {
      size: [6, 0], // Show markers only for main line
      colors: [blueColor],
      strokeColors: "#ffffff",
      strokeWidth: 2,
      hover: {
        size: 8,
      },
    };
  } else {
    options.markers = {
      size: 6,
      colors: [blueColor],
      strokeColors: "#ffffff",
      strokeWidth: 2,
      hover: {
        size: 8,
      },
    };
  }

  return options;
});

onMounted(() => {
  setTimeout(() => (ready.value = true), 0);
});
</script>

<template>
  <div class="chart-container">
    <div class="mb-3 flex items-center justify-between">
      <h4 class="font-semibold">{{ title }}</h4>
      <div class="mr-1">
        <ProgressSpinner v-if="loading" class="!size-5" />
      </div>
    </div>
    <div class="relative rounded-xl border border-lightgrey p-4 shadow-md dark:border-slate-600">
      <ApexChart v-if="ready" :options="chartOptions" :series="series" :height="height" />
      <div
        v-if="!data?.results || data.results.length === 0"
        class="z-2 absolute inset-0 flex items-center justify-center rounded-xl bg-black bg-opacity-30 p-5"
      >
        <p class="transform text-center text-xl font-bold text-white md:text-2xl">No data available yet.</p>
      </div>
    </div>
  </div>
</template>
