<script setup lang="ts">
import { QuestionMarkCircleIcon } from "@heroicons/vue/24/outline";
import AttestationProgressBar from "./common/AttestationProgressBar.vue";

interface CodeAttestationValue {
  url?: string;
  percentage: number;
}

const props = defineProps<{
  codeAttestationPercentages: Object;
}>();

const codeAttestationPercentages = props.codeAttestationPercentages as Record<string, CodeAttestationValue>;
</script>

<template>
  <div>
    <hr class="my-5" />
    <div
      class="relative my-5 rounded-md border border-gray-200 bg-white p-4 dark:border-slate-600 dark:bg-slate-900 sm:m-auto sm:w-1/2"
    >
      <table class="min-w-full text-left text-sm font-light">
        <thead class="gray:border-neutral-200 h-10 border-b font-medium">
          <tr>
            <th class="w-1/3">Area</th>
            <th>
              Code Attestation
              <div
                class="ml-1 inline-block"
                data-te-toggle="popover"
                data-te-title="Code Attestation Progress"
                data-te-content="Based on All Time"
                data-te-trigger="hover focus"
              >
                <QuestionMarkCircleIcon class="inline w-5 cursor-help opacity-80" />
              </div>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(value, label) in codeAttestationPercentages" :key="label" class="h-8">
            <td>
              <template v-if="value.url">
                <a class="underline" :href="value.url">{{ label }}</a>
              </template>
              <template v-else>
                <span>{{ label }}</span>
              </template>
            </td>
            <td>
              <AttestationProgressBar
                :progress="value.percentage"
                :max="100"
                :content="`${value.percentage.toFixed(2)}%`"
              />
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
