<script setup lang="ts">
import { toHumanReadableDate } from "@/compass/helpers/utils";
import { computed } from "vue";
import type { RouteLocationRaw } from "vue-router";

// those are all optional because the slots that are using them are overridable
const props = defineProps<{
  title?: string;
  updatedAt?: number;
  urlLabel?: string;
  href?: string;
  to?: RouteLocationRaw;
  loading?: boolean;
  beta?: boolean;
  tiny?: boolean;
}>();

const updatedAtHumanReadable = computed(() => toHumanReadableDate(props.updatedAt));

const linkProps = computed(() => {
  if (props.href) return { href: props.href };
  if (props.to) return { to: props.to };
  return {};
});
</script>

<template>
  <section class="rounded-lg bg-white p-6 shadow dark:bg-slate-900" :class="{ 'flex flex-col justify-between': tiny }">
    <div>
      <slot name="header">
        <div
          class="flex flex-col justify-between gap-0.5 sm:flex-row sm:items-center"
          :class="{ '!flex-col !items-start': tiny }"
        >
          <h2 class="text-xl font-semibold">{{ title }} <sup v-if="beta">BETA</sup></h2>
          <div v-if="props.updatedAt" class="text-gray-600">Last updated: {{ updatedAtHumanReadable }}</div>
          <div v-else-if="loading" class="flex items-center gap-2">
            <ProgressSpinner class="!size-4" />
          </div>
        </div>
      </slot>
      <div class="my-6">
        <ProgressSpinner v-if="loading" class="!size-8" />
        <slot v-else />
      </div>
    </div>
    <div>
      <slot v-if="!loading" name="footer">
        <Button as="router-link" v-bind="linkProps" :label="urlLabel" size="small" variant="link" class="!p-0" />
      </slot>
    </div>
  </section>
</template>
