<script setup lang="ts">
import { snakeCase } from "lodash";

const props = defineProps<{
  title: string;
  data: any;
}>();

const escapeCell = (value: string | number) => {
  if (typeof value === "number") return value;
  return '"' + String(value).replace(/"/g, '""') + '"';
};

const exportCsv = () => {
  const series = props.data.series[0];
  const csvData = [["Date", series.name, props.data.extraData.name]];
  props.data.categories.forEach(function (category: string, index: number) {
    const extraDataValue = props.data.extraData.series[0][category];

    csvData.push([
      category,
      series.data[index],
      Array.isArray(extraDataValue) ? extraDataValue.join(", ") : extraDataValue,
    ]);
  });

  const csvContent = csvData.map((row) => row.map(escapeCell).join(",")).join("\n");
  const blob = new Blob([csvContent], { type: "text/csv" });
  const url = URL.createObjectURL(blob);

  const a = document.createElement("a");
  a.href = url;
  a.download = snakeCase(props.title) + ".csv";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);

  URL.revokeObjectURL(url);
};
</script>

<template>
  <Button label="Export as CSV" class="w-full" size="small" @click="exportCsv" />
</template>
