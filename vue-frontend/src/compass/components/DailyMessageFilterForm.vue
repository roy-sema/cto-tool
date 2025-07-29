<script setup lang="ts">
import MultiSelectWithButtons from "@/aicm/components/common/MultiSelectWithButtons.vue";
import { getDailyMessageFilter, updateDailyMessageFilter } from "@/compass/helpers/api";
import type {
  DailyMessageFilterOption,
  DailyMessageFilterResponse,
  DailyMessageTicketCategory,
  MessageFilter,
  OrganizationRepositoryGroup,
} from "@/compass/helpers/api.d";
import { InformationCircleIcon } from "@heroicons/vue/24/outline";
import * as Sentry from "@sentry/vue";
import { onMounted, ref } from "vue";

const { showSave = true } = defineProps<{
  showSave?: boolean;
}>();

const emit = defineEmits<{
  (e: "filtersChanged", payload?: any): void;
}>();

const loading = ref(true);
const updateLoading = ref(false);
const formChanged = ref(false);

const selectedFilter = ref<MessageFilter>({
  significance_levels: [],
  repository_groups: [],
  ticket_categories: [],
  day_interval: 0,
});

const allSignificanceLevels = ref<DailyMessageFilterOption[]>([]);
const repositoryGroups = ref<OrganizationRepositoryGroup[]>([]);
const ticketCategories = ref<DailyMessageTicketCategory[]>([]);

const loadData = async () => {
  try {
    const response = await getDailyMessageFilter();
    updateData(response);
  } catch (error) {
    Sentry.captureException(error);
  } finally {
    loading.value = false;
  }
};

const submitForm = async () => {
  try {
    updateLoading.value = true;
    const messageFilter = await updateDailyMessageFilter(selectedFilter.value);
    updateData(messageFilter);
  } catch (error) {
    Sentry.captureException(error);
  } finally {
    updateLoading.value = false;
  }
};

const applyFilter = async () => {
  emit("filtersChanged", selectedFilter.value);
  formChanged.value = false;
};

const onFormChanged = () => (formChanged.value = true);

const updateData = (messageFilter: DailyMessageFilterResponse) => {
  allSignificanceLevels.value = messageFilter.options.significance_levels;
  repositoryGroups.value = messageFilter.options.repository_groups;
  ticketCategories.value = messageFilter.options.ticket_categories;
  selectedFilter.value = messageFilter.daily_message_filter;
  formChanged.value = true;
};

onMounted(() => {
  loadData();
});
</script>

<template>
  <div class="my-5 flex flex-col">
    <div class="mx-auto w-full max-w-3xl">
      <Card>
        <template #content>
          <div v-if="loading" class="flex justify-center">
            <ProgressSpinner class="!size-10" />
          </div>
          <div v-else>
            <div v-if="showSave" class="mb-5">
              <h2 class="text-lg font-semibold">Personalize your daily message</h2>
              <div class="text-xs text-muted-color">Changes made will be reflected in the next daily message</div>
            </div>
            <form class="grid grid-cols-2 items-center gap-x-4 gap-y-4">
              <div class="flex items-center gap-1">
                Significance Levels
                <InformationCircleIcon
                  v-tooltip.top="{
                    value:
                      '10 point significance score where 10 = highest and only 7-10s are shown. Typically, individual teams should know about all of the 7s in their area of focus. 9s and 10s may be suitable for CTO/ CPO discussion. Insights with scores lower than 7 are too insignificant to be useful.',
                    escape: false,
                    autoHide: false,
                    pt: { text: 'text-xs' },
                  }"
                  class="size-4 cursor-pointer text-blue"
                />
              </div>
              <MultiSelectWithButtons
                v-model="selectedFilter.significance_levels"
                :options="allSignificanceLevels"
                placeholder="Select significance levels"
                @change="onFormChanged"
              />

              <div>Repository Groups</div>
              <MultiSelectWithButtons
                v-model="selectedFilter.repository_groups"
                :options="repositoryGroups"
                optionValue="public_id"
                placeholder="Select Repository Groups"
                @change="onFormChanged"
              />

              <div>Ticket Categories</div>
              <MultiSelectWithButtons
                v-model="selectedFilter.ticket_categories"
                :options="ticketCategories"
                placeholder="Select Ticket Categories"
                @change="onFormChanged"
              />

              <Button
                class="col-span-2 mt-5"
                :severity="formChanged ? 'primary' : 'secondary'"
                :label="showSave ? 'Save' : 'Apply'"
                :loading="updateLoading"
                @click="showSave ? submitForm() : applyFilter()"
              />
            </form>
          </div>
        </template>
      </Card>
    </div>
  </div>
</template>
