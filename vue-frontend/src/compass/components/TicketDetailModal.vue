<script setup lang="ts">
import { getTicketCompletenessTicket } from "@/compass/helpers/api";
import type { TicketCompletenessTicketResponse } from "@/compass/helpers/api.d";
import { ArrowTopRightOnSquareIcon, CpuChipIcon } from "@heroicons/vue/24/outline";
import * as Sentry from "@sentry/vue";
import { computed, ref, watch } from "vue";
// @ts-ignore
import MarkdownIt from "markdown-it";

const props = defineProps<{
  visible: boolean;
  ticketId: string | null;
}>();

const emit = defineEmits<{
  "update:visible": [value: boolean];
}>();

const loading = ref(false);
const ticketData = ref<TicketCompletenessTicketResponse | null>(null);
const isAccordionExpanded = ref(false);
const activeAccordionIndex = ref(-1);

watch(activeAccordionIndex, (newIndex) => {
  isAccordionExpanded.value = newIndex === 0;
});

const updateVisibility = (value: boolean) => {
  emit("update:visible", value);
  if (!value) {
    activeAccordionIndex.value = -1;
  }
};

const handleKeydown = (event: KeyboardEvent) => {
  if (event.key === "Escape" && props.visible) {
    updateVisibility(false);
  }
};

const openInJira = () => {
  if (ticketData.value?.jira_url) {
    window.open(ticketData.value.jira_url, "_blank");
  }
};

const loadTicketData = async () => {
  if (!props.ticketId) return;

  try {
    loading.value = true;
    const response = await getTicketCompletenessTicket(props.ticketId);
    ticketData.value = response;
  } catch (error) {
    Sentry.captureException(error);
  } finally {
    loading.value = false;
  }
};

const md = new MarkdownIt({
  html: true,
  linkify: true,
  typographer: true,
  breaks: true,
});

const parseMarkdown = (text: string): string => {
  if (!text) return "";

  try {
    return md.render(text);
  } catch (error) {
    Sentry.captureException(error);
    return text;
  }
};

const formattedDescription = computed(() => {
  if (!ticketData.value?.current_data.description) {
    return "No description available.";
  }
  return parseMarkdown(ticketData.value.current_data.description);
});

const scoreColor = computed(() => {
  if (!ticketData.value?.current_data.quality_category) return "text-blue-600";
  const colorMap: Record<string, string> = {
    Initial: "text-red-600",
    Emerging: "text-orange-600",
    Mature: "text-yellow-600",
    Advanced: "text-green-600",
  };
  return colorMap[ticketData.value.current_data.quality_category] || "text-blue-600";
});

const formatExplanation = (text: string): string => {
  if (!text) return "";

  return parseMarkdown(text);
};

const formattedScoreHistory = computed(() => {
  if (!ticketData.value?.scores_history || ticketData.value.scores_history.length === 0) {
    return null;
  }

  const history = [...ticketData.value.scores_history];
  const currentDate = new Date(history[0].date);
  const firstDate = new Date(history[history.length - 1].date);
  const daysDiff = Math.floor((currentDate.getTime() - firstDate.getTime()) / (1000 * 60 * 60 * 24));
  const weeksDiff = Math.floor(daysDiff / 7);

  let timeToCurrent = "";
  if (weeksDiff > 0) {
    timeToCurrent = `${weeksDiff} week${weeksDiff > 1 ? "s" : ""}`;
  } else if (daysDiff > 0) {
    timeToCurrent = `${daysDiff} day${daysDiff > 1 ? "s" : ""}`;
  } else {
    timeToCurrent = "Today";
  }

  const formattedEntries = history.map((entry, index) => {
    const date = new Date(entry.date);
    const formattedDate = date.toLocaleDateString("en-US", {
      weekday: "short",
      month: "short",
      day: "numeric",
    });

    let scoreChange = "";
    let changeColor = "";
    if (index < history.length - 1) {
      const nextScore = history[index + 1].score;
      const change = entry.score - nextScore;
      if (change > 0) {
        scoreChange = ` +${change}`;
        changeColor = "text-green-600";
      } else if (change < 0) {
        scoreChange = ` ${change}`;
        changeColor = "text-red-600";
      }
    }

    return {
      date: formattedDate,
      score: entry.score,
      change: scoreChange,
      changeColor: changeColor,
    };
  });

  return {
    timeToCurrent,
    entries: formattedEntries,
  };
});

watch(
  () => [props.visible, props.ticketId],
  ([visible, ticketId]) => {
    if (visible && ticketId) {
      loadTicketData();
    }
  },
  { immediate: true },
);

watch(
  () => props.visible,
  (visible) => {
    if (visible) {
      document.addEventListener("keydown", handleKeydown);
    } else {
      document.removeEventListener("keydown", handleKeydown);
    }
  },
  { immediate: true },
);
</script>

<template>
  <Dialog
    modal
    class="mx-4 lg:w-3/4 xl:w-2/3"
    :visible="visible"
    header="Ticket Details"
    :closable="false"
    @update:visible="updateVisibility"
  >
    <div v-if="loading" class="flex justify-center py-8">
      <ProgressSpinner class="!size-10" />
    </div>

    <div v-else-if="!ticketData" class="py-8 text-center text-gray-500">No ticket data found.</div>

    <div v-else class="space-y-6">
      <div class="flex items-start justify-between">
        <div>
          <h3 class="text-xl font-semibold">{{ ticketData.current_data.ticket_id }}</h3>
          <p class="text-sm text-gray-500">{{ ticketData.current_data.name }}</p>
        </div>
        <div class="flex items-center gap-2">
          <Tag :value="ticketData.current_data.llm_category" severity="secondary" />
          <Tag :value="ticketData.current_data.stage" severity="warning" />
        </div>
      </div>

      <div class="grid gap-6 md:grid-cols-2">
        <div class="h-fit rounded-lg border border-gray-200 p-4 dark:border-slate-600">
          <h4 class="mb-3 font-semibold">Description</h4>
          <div
            class="markdown-content max-h-64 overflow-y-auto text-sm text-gray-700 dark:text-gray-300"
            v-html="formattedDescription"
          ></div>
        </div>

        <div class="rounded-lg border border-gray-200 p-4 dark:border-slate-600">
          <h4 class="mb-3 font-semibold">TCS Score Analysis</h4>

          <div class="mb-4">
            <div class="flex items-center gap-2">
              <span class="text-2xl font-bold" :class="scoreColor">Overall Score:</span>
              <span class="text-2xl font-bold" :class="scoreColor">
                {{ ticketData.current_data.completeness_score }}/100
              </span>
            </div>
            <div class="mt-1 text-sm text-gray-500">{{ ticketData.current_data.quality_category }}</div>
          </div>

          <div class="mb-4 rounded-lg border bg-gray-50 p-4 dark:bg-slate-800">
            <Accordion v-model:activeIndex="activeAccordionIndex">
              <AccordionTab>
                <template #header>
                  <div class="flex flex-col gap-1">
                    <div class="flex items-center gap-2">
                      <span>Analysis</span>
                      <span class="text-sm text-gray-500">Detailed breakdown</span>
                    </div>
                    <div
                      v-if="!isAccordionExpanded && ticketData.current_data.completeness_score_explanation"
                      class="line-clamp-1 text-xs text-gray-500"
                      v-html="
                        formatExplanation(ticketData.current_data.completeness_score_explanation).substring(0, 50) +
                        '...'
                      "
                    ></div>
                  </div>
                </template>
                <div
                  class="flex items-start gap-2 rounded bg-sky-300 p-3 text-sm text-gray-700 dark:bg-sky-600 dark:text-gray-300"
                >
                  <div class="flex-shrink-0">
                    <CpuChipIcon class="text-blue-500 h-5 w-5" />
                  </div>
                  <span v-html="formatExplanation(ticketData.current_data.completeness_score_explanation)"></span>
                </div>
              </AccordionTab>
            </Accordion>
          </div>

          <div v-if="formattedScoreHistory" class="mb-4">
            <h5 class="mb-3 font-semibold">Score Progress History</h5>
            <div class="mb-1 text-sm text-gray-500">
              Time to Current Score: {{ formattedScoreHistory.timeToCurrent }}
            </div>
            <div class="space-y-1 font-mono text-sm text-gray-500">
              <div v-for="entry in formattedScoreHistory.entries" :key="entry.date" class="flex justify-between">
                <span>{{ entry.date }}</span>
                <span class="font-semibold">
                  {{ entry.score }}
                  <span v-if="entry.change" :class="entry.changeColor">{{ entry.change }}</span>
                </span>
              </div>
            </div>
            <h6 class="mt-4 font-semibold">Project Key</h6>
            <div class="mb-1 text-sm text-gray-500">
              {{ ticketData.current_data.project_key }}
            </div>
            <h6 class="mt-4 font-semibold">Assignee</h6>
            <div class="mb-1 text-sm text-gray-500">
              {{ ticketData.current_data.assignee || "Unassigned" }}
            </div>

            <div v-if="ticketData.jira_url" class="mt-4">
              <Button
                label="Open in Jira"
                severity="primary"
                size="small"
                class="bg-blue-600 hover:bg-blue-700 border-blue-600 hover:border-blue-700 w-full"
                @click="openInJira"
              >
                <template #icon>
                  <ArrowTopRightOnSquareIcon class="size-4" />
                </template>
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <template #footer>
      <div class="flex justify-end">
        <Button label="Close" severity="secondary" @click="updateVisibility(false)" />
      </div>
    </template>
  </Dialog>
</template>

<style scoped>
/* Target dynamically rendered markdown content only within specific containers */
.markdown-content :deep(h1) {
  @apply mb-4 mt-6 text-3xl font-bold text-gray-900 dark:text-gray-100;
}

.markdown-content :deep(h2) {
  @apply mb-3 mt-5 text-2xl font-bold text-gray-900 dark:text-gray-100;
}

.markdown-content :deep(h3) {
  @apply mb-3 mt-4 text-xl font-bold text-gray-900 dark:text-gray-100;
}

.markdown-content :deep(h4) {
  @apply mb-2 mt-3 text-lg font-bold text-gray-900 dark:text-gray-100;
}

.markdown-content :deep(h5) {
  @apply mb-2 mt-3 text-base font-bold text-gray-900 dark:text-gray-100;
}

.markdown-content :deep(h6) {
  @apply mb-2 mt-3 text-sm font-bold text-gray-900 dark:text-gray-100;
}

.markdown-content :deep(strong) {
  @apply font-bold text-gray-900 dark:text-gray-100;
}

.markdown-content :deep(em) {
  @apply italic text-gray-700 dark:text-gray-300;
}

.markdown-content :deep(code) {
  @apply rounded bg-gray-100 px-1 py-0.5 font-mono text-sm dark:bg-gray-700;
}

.markdown-content :deep(ul) {
  @apply mb-4 ml-6 list-disc space-y-1;
}

.markdown-content :deep(ol) {
  @apply mb-4 ml-6 list-decimal space-y-1;
}

.markdown-content :deep(li) {
  @apply leading-relaxed text-gray-700 dark:text-gray-300;
}
</style>
