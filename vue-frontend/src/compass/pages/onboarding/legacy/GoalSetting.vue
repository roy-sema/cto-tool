<script setup lang="ts">
import { computed, ref } from "vue";
import { useRouter } from "vue-router";

const router = useRouter();

const insightField = ref("");
const isEmptyInsight = computed(() => insightField.value.trim() === "");

const submit = () => {
  if (isEmptyInsight.value) {
    return;
  }

  // TODO: send request to backend?

  router.push({ name: "onboarding-goal-setting-step-2" });
};
</script>

<template>
  <div class="centered-wrapper -mt-10">
    <div class="mx-auto w-full px-4 md:w-2/3 lg:px-6">
      <Panel>
        <template #header>
          <div>
            <h2 class="text-lg font-semibold">Name Your Insight</h2>
            <p class="mt-1 text-sm text-muted-color">Give your insight a descriptive name</p>
          </div>
        </template>

        <InputText
          v-model="insightField"
          placeholder="e.g., Q1 2024 Engineering Roadmap Insight"
          class="w-full"
          autofocus
        />

        <div class="mt-5 flex justify-end">
          <Button label="Continue" severity="contrast" :disabled="isEmptyInsight" @click="submit" />
        </div>
      </Panel>
    </div>
  </div>
</template>

<style scoped>
.p-progressbar {
  background-color: transparent;
}

:deep(.p-progressbar-value) {
  border-radius: var(--p-progressbar-border-radius);
}
</style>
