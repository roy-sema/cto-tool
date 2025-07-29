<script setup lang="ts">
import ActionPanel from "@/compass/components/sip/ActionPanel.vue";
import LearnMoreDialog from "@/compass/components/sip/LearnMoreDialog.vue";
import { Clock } from "lucide-vue-next";
import type { Component } from "vue";
import { computed, ref } from "vue";
import { useRouter } from "vue-router";

const props = defineProps<{
  title: string;
  icon: Component;
  value: number | string;
  metric: string;
  description: string;
  color: string;
  comingSoon?: boolean;
  href?: string;
  loading?: boolean;
  to?: string;
}>();

const router = useRouter();

const modalVisible = ref(false);

const colorMap = {
  red: "text-red-600",
  orange: "text-orange-400",
  yellow: "text-yellow-400",
  green: "text-green-600",
  gray: "text-muted-color",
};

// TODO: re-enable color
// const colorClass = computed(() => colorMap[props.color as keyof typeof colorMap] || colorMap["green"]);
const colorClass = computed(() => (props.comingSoon ? colorMap["gray"] : null));

const handleClick = () => {
  if (props.comingSoon) modalVisible.value = true;
  else if (props.to) router.push({ name: props.to });
  else if (props.href) window.location.href = props.href;
};
</script>

<template>
  <ActionPanel :title="title" :icon="icon" :disabled="comingSoon" @click="handleClick">
    <div class="mb-4">
      <div class="flex items-baseline space-x-2">
        <div v-if="loading" class="-mt-0.5">
          <ProgressSpinner class="!size-8" />
        </div>
        <span v-else class="text-3xl font-bold" :class="colorClass">
          {{ value }}
        </span>
        <span class="text-sm text-gray-500">{{ metric }}</span>
      </div>
      <p class="mt-1 text-sm text-gray-600">{{ description }}</p>
    </div>
    <div v-if="comingSoon" class="flex items-center space-x-2 text-sky-600">
      <Clock class="size-4" />
      <span class="text-sm font-medium">Coming Soon</span>
    </div>
  </ActionPanel>

  <LearnMoreDialog v-if="comingSoon" v-model:visible="modalVisible" :product="title" />
</template>
