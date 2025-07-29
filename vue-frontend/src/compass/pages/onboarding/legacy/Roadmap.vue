<script setup lang="ts">
import RoadmapItemForm from "@/compass/components/RoadmapItemForm.vue";
import { getOrganizationDeveloperGroups } from "@/compass/helpers/api";
import type { OrganizationDeveloperGroup, RoadmapItem } from "@/compass/helpers/api.d";
import { PlusIcon } from "@heroicons/vue/24/outline";
import * as Sentry from "@sentry/vue";
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";

const router = useRouter();

const loading = ref(true);
const items = ref<RoadmapItem[]>([]);
const teams = ref<OrganizationDeveloperGroup[]>([]);

const addRoadmapItem = () => {
  items.value.push({
    name: "",
    teams: [],
    startDate: null,
    endDate: null,
    description: "",
  });
};

const loadTeams = async () => {
  try {
    loading.value = true;

    const response = await getOrganizationDeveloperGroups();
    teams.value = response.developer_groups;
  } catch (error) {
    Sentry.captureException(error);
  } finally {
    loading.value = false;
  }
};

onMounted(() => {
  addRoadmapItem();
  loadTeams();
});
</script>

<template>
  <div class="centered-wrapper flex flex-col gap-5 py-10">
    <div class="mx-auto w-full px-4 md:w-3/4 lg:px-6 xl:w-2/3">
      <Panel>
        <template #header>
          <div>
            <h2 class="text-lg font-semibold">Add Roadmap Item</h2>
          </div>
        </template>

        <div class="flex flex-col gap-5">
          <RoadmapItemForm
            v-for="(item, index) in items"
            :key="index"
            :item="item"
            :teams="teams"
            :loading="loading"
            @remove="items.splice(index, 1)"
          />
        </div>

        <div v-if="!items.length">
          <div class="text-center text-muted-color">No roadmap items added yet.</div>
        </div>

        <div class="mt-5">
          <Button label="Add Another Roadmap Item" severity="contrast" class="w-full" @click="addRoadmapItem">
            <template #icon>
              <PlusIcon class="size-5" />
            </template>
          </Button>
        </div>
      </Panel>
    </div>

    <div>
      <Button label="Next" @click="router.push({ name: 'onboarding-connect-jira' })" />
    </div>
  </div>
</template>
