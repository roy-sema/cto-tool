<script setup lang="ts">
import type { OrganizationDeveloperGroup, RoadmapItem } from "@/compass/helpers/api.d";
import { TrashIcon } from "@heroicons/vue/24/outline";

defineProps<{
  item: RoadmapItem;
  teams: OrganizationDeveloperGroup[];
  loading?: boolean;
}>();

defineEmits(["remove"]);
</script>

<template>
  <div class="rounded-md border px-3 py-2 dark:border-slate-600">
    <div class="grid gap-5 sm:grid-cols-2">
      <label class="flex w-full flex-col gap-1">
        <div class="font-semibold">Name</div>
        <InputText v-model="item.name" placeholder="Type name" class="w-full" />
      </label>

      <label class="flex w-full flex-col gap-1">
        <div class="font-semibold">Team(s)</div>
        <MultiSelect
          v-model="item.teams"
          :loading="loading"
          :options="teams"
          optionLabel="name"
          filter
          placeholder="Choose team(s)"
          :maxSelectedLabels="3"
        />
      </label>
    </div>

    <div class="mt-5 grid gap-5 sm:grid-cols-2">
      <label class="flex w-full flex-col gap-1">
        <div class="font-semibold">Planned Start Date</div>
        <DatePicker v-model="item.startDate" showIcon iconDisplay="input" placeholder="MM/DD/YYYY" />
      </label>

      <label class="flex w-full flex-col gap-1">
        <div class="font-semibold">Planned End Date</div>
        <DatePicker v-model="item.endDate" showIcon iconDisplay="input" placeholder="MM/DD/YYYY" />
      </label>
    </div>

    <div class="mt-5">
      <label class="flex w-full flex-col gap-1">
        <div class="font-semibold">
          Description / Context
          <span class="text-sm font-light text-muted-color">(optional)</span>
        </div>
        <Textarea v-model="item.description" rows="5" placeholder="Type description" />
      </label>
    </div>

    <div class="mt-2 flex justify-end">
      <Button label="Remove item" severity="secondary" size="small" text @click="$emit('remove')">
        <template #icon>
          <TrashIcon class="size-5" />
        </template>
      </Button>
    </div>
  </div>
</template>
