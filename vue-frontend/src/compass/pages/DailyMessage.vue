<script setup lang="ts">
import PageHeader from "@/compass/components/common/PageHeader.vue";
import DailyMessageFilterForm from "@/compass/components/DailyMessageFilterForm.vue";
import { getDailyMessage } from "@/compass/helpers/api";
import type { MessageFilter } from "@/compass/helpers/api.d";
import * as Sentry from "@sentry/vue";
import { useToast } from "primevue/usetoast";
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

const route = useRoute();
const router = useRouter();
const toast = useToast();

const loading = ref(true);
const message = ref<string>();
const date = ref<Date>(new Date());
const maxDate = computed(() => new Date());

const messageContainer = ref<HTMLElement | null>(null);
const sectionId = route.query.section as string | undefined;

const selectedFilter = ref<MessageFilter>();

const loadData = async () => {
  try {
    loading.value = true;

    const asEmail = route.query["as-email"] === "true";
    const response = await getDailyMessage(date.value, asEmail, selectedFilter.value);

    message.value = response.content;
  } catch (error) {
    Sentry.captureException(error);
  } finally {
    loading.value = false;
  }
};

const updateByFilter = async (payload: MessageFilter) => {
  selectedFilter.value = payload;
  await loadData();
};

watch(message, async (newMessage) => {
  if (!newMessage || !sectionId) return;

  setTimeout(() => {
    if (messageContainer.value) {
      const target = messageContainer.value.querySelector(`#${sectionId}`);
      if (target) {
        target.scrollIntoView({ behavior: "smooth", block: "start" });
        if (target.tagName === "DETAILS") {
          (target as HTMLDetailsElement).open = true;
        }
      }
    }
  }, 50);
});

watch(date, (newDate) => {
  const localDate = newDate.toLocaleDateString("en-CA"); // YYYY-MM-DD
  router.replace({ query: { ...route.query, date: localDate } });
});

onMounted(() => {
  const queryDate = route.query.date as string;
  if (queryDate && !isNaN(new Date(queryDate).getTime())) date.value = new Date(queryDate);
  loadData();
});

// @ts-ignore
window.copyText = function (id: string) {
  const el = document.getElementById(id);

  if (!el) {
    Sentry.withScope((scope) => {
      scope.setTag("component", "DailyMessage");
      scope.setLevel("error");
      scope.setExtra("element_id", id);
      scope.setExtra("html", message.value);
      Sentry.captureException(new Error("Couldn't determine element ID."));
    });

    toast.add({
      severity: "error",
      summary: "Copy failed. Try again later",
      life: 10000,
    });
    return;
  }

  // Hide/show elements during copy to clipboard.
  const noCopyElements = el.querySelectorAll(".no-copy-clipboard");
  noCopyElements.forEach((element) => ((element as HTMLElement).style.display = "none"));

  const copyElements = el.querySelectorAll(".copy-clipboard-only");
  copyElements.forEach((element) => ((element as HTMLElement).style.display = ""));

  const text = el?.innerText || "";

  // Revert hide/show elements after copy to clipboard.
  noCopyElements.forEach((element) => ((element as HTMLElement).style.display = ""));
  copyElements.forEach((element) => ((element as HTMLElement).style.display = "none"));

  navigator.clipboard
    .writeText(text)
    .then(() => {
      toast.add({
        severity: "success",
        summary: `Copied ${id.split("--")[0]}`,
        life: 10000,
      });
    })
    .catch((err) => {
      toast.add({
        severity: "error",
        summary: "Copy failed: " + err,
        life: 10000,
      });
    });
};
</script>

<template>
  <PageHeader title="Daily Message" :updatedAt="null" />
  <Toast />
  <div class="sip mx-auto mt-5 flex max-w-screen-xl flex-col gap-4 px-4">
    <div class="grid gap-5 sm:grid-cols-2">
      <div>
        <FloatLabel variant="in">
          <DatePicker
            v-model="date"
            showIcon
            iconDisplay="input"
            dateFormat="mm/dd/yy"
            :maxDate="maxDate"
            :manualInput="false"
            class="w-full"
            @update:modelValue="loadData"
          />
          <label for="in_label">Date</label>
        </FloatLabel>
        <DailyMessageFilterForm :showSave="false" @filtersChanged="updateByFilter" />
      </div>
      <a
        class="self-end justify-self-end text-sm font-semibold text-blue hover:text-violet dark:hover:text-lightgrey"
        href="/settings/insights-notifications/"
      >
        Personalize your daily email
      </a>
    </div>
    <ProgressSpinner v-if="loading" class="!size-14" />
    <!-- HACK this is a hack so the message is readable in dark mode -->
    <div
      v-else-if="message"
      ref="messageContainer"
      class="rounded-md border border-gray-200 bg-white p-2 text-black dark:border-slate-600"
      v-html="message"
    />
    <div v-else class="text-gray-500">An Error has occurred while loading the daily message</div>
  </div>
</template>
