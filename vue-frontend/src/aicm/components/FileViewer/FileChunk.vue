<script setup lang="ts">
import AttestationForm from "@/aicm/components/AttestationForm.vue";
import IconButton from "@/aicm/components/common/IconButton.vue";
import TextButton from "@/aicm/components/common/TextButton.vue";
import TWESpinner from "@/aicm/components/common/TWESpinner.vue";
import { attestChunk } from "@/aicm/helpers/api";
import type { RepositoryCodeAttestation, RepositoryFileChunk } from "@/aicm/helpers/api.d";
import { CheckIcon, CpuChipIcon, NoSymbolIcon, UserCircleIcon, XMarkIcon } from "@heroicons/vue/24/outline";
import * as Sentry from "@sentry/vue";
import { Popover, initTWE } from "tw-elements";
import type { Component } from "vue";
import { computed, onMounted, ref, watch } from "vue";

const props = defineProps<{
  chunk: RepositoryFileChunk;
  codeGenerationLabels: { [key: string]: string };
  attestationLabels: { [key: string]: string };
  repositoryId: string;
  showBlame?: boolean;
  shredded?: boolean;
}>();

const emit = defineEmits(["attested"]);
const isNotEvaluated = computed(() => props.chunk.label == "not_evaluated");

const Icon = computed(() => {
  const iconMap: { [key: string]: Component } = {
    human: UserCircleIcon,
    not_evaluated: NoSymbolIcon,
    ai: CpuChipIcon,
    blended: CpuChipIcon,
    default: CpuChipIcon,
  };

  return iconMap[props.chunk.label || "default"];
});

// while files are being reloaded, use tmpAttestation to show the new attestation
const tmpAttestation = ref<RepositoryCodeAttestation | null>(null);
const attestation = computed(() => tmpAttestation.value || props.chunk.attestation);
const currentLabel = computed(() => attestation.value?.label || props.chunk.label);

// unset tmpAttestation when attestation changes, which means it was updated
watch(
  () => props.chunk.attestation,
  () => (tmpAttestation.value = null),
);

const attesting = ref(false);
const loading = ref(false);
const attestError = ref(false);

const code = computed(() => {
  let blameIndex = 0;
  const chunk = props.chunk;
  const blames = chunk.blames;

  return chunk.code.map((line, index) => {
    const lineIndex = chunk.code_line_start + index;

    while (blameIndex < blames.length - 1 && lineIndex > blames[blameIndex].code_line_end) blameIndex++;

    const blame = blames[blameIndex];
    const author = blame?.author ?? "-";

    return { author: author, index: lineIndex, line: line };
  });
});

// Legacy chunks have no code hash and cannot be attested
const showAttestButtons = computed(
  () =>
    !loading.value && !attestation.value && !attesting.value && props.chunk.code_hash !== null && !isNotEvaluated.value,
);

const confirmLabel = async () => attest(props.chunk.label);

const changeLabel = async (label: string, comment: string) => {
  return attest(label, comment);
};

const attest = async (label: string, comment?: string) => {
  loading.value = true;
  attestError.value = false;
  try {
    const attestation = await attestChunk(props.repositoryId, props.chunk.code_hash, label, comment);

    // use copy until chunk is updated
    tmpAttestation.value = attestation;

    emit("attested");

    attesting.value = false;
  } catch (error) {
    Sentry.captureException(error);
    attestError.value = true;
    attesting.value = true;
  } finally {
    loading.value = false;
  }
};

const formatDate = (str: string) => {
  const date = new Date(str);

  const year = date.getFullYear();
  const month = ("0" + (date.getMonth() + 1)).slice(-2);
  const day = ("0" + date.getDate()).slice(-2);
  const hours = ("0" + date.getHours()).slice(-2);
  const minutes = ("0" + date.getMinutes()).slice(-2);

  return `${year}-${month}-${day} ${hours}:${minutes}`;
};

onMounted(() => {
  initTWE({ Popover }, { allowReinits: true });
});
</script>

<template>
  <div class="chunk mb-3 overflow-hidden rounded-xl border border-gray-200 dark:border-slate-600">
    <div
      class="flex h-11 items-center justify-between border-b border-gray-200 px-3 py-2 text-xs shadow-sm dark:border-slate-600"
    >
      <div class="flex items-center gap-2">
        <Icon class="inline w-4 md:w-5" />

        <span class="mr-1 font-semibold">
          {{ props.codeGenerationLabels[currentLabel] }}
        </span>

        <TWESpinner v-if="loading" :size="4" />

        <AttestationForm
          v-else-if="attesting"
          :chunk="chunk"
          :attestationLabels
          :selectedLabel="currentLabel"
          @cancel="attesting = false"
          @submit="changeLabel"
        />

        <div v-show="showAttestButtons" class="flex items-center gap-1">
          <IconButton
            :icon="CheckIcon"
            :size="4"
            data-twe-toggle="popover"
            data-twe-trigger="hover"
            data-twe-content="Attest by Agreeing with the label"
            data-twe-placement="top"
            @click="confirmLabel"
          />
          <IconButton
            :icon="XMarkIcon"
            :size="4"
            data-twe-toggle="popover"
            data-twe-trigger="hover"
            data-twe-content="Attest by Overriding the label"
            data-twe-placement="top"
            @click="attesting = true"
          />
        </div>
      </div>

      <div v-if="!attesting">
        <div v-if="attestation" class="flex gap-2 text-gray-500">
          <span> Attested by {{ attestation.attested_by.full_name }} at {{ formatDate(attestation.updated_at) }} </span>
          <span>·</span>
          <TextButton text="Edit" @click.prevent="attesting = true" />
        </div>
        <span v-else-if="!isNotEvaluated" class="text-gray-500">Not attested</span>
      </div>
      <div v-else-if="attestError" class="text-red-500">Error attesting, please try again</div>
    </div>

    <div class="overflow-x-auto shadow-md">
      <table class="whitespace-pre font-mono text-xs">
        <tr
          v-for="({ author, index, line }, idx) in code"
          :key="index"
          :class="{
            'border-t border-dotted border-gray-300 dark:border-slate-600':
              idx > 0 && code[idx - 1]?.author !== author && showBlame,
          }"
        >
          <td
            v-if="showBlame"
            class="min-w-28 max-w-28 select-none overflow-clip overflow-ellipsis px-2 py-0.5 text-center align-baseline"
            :title="author"
          >
            <template v-if="code[idx - 1]?.author !== author">{{ author }}</template>
          </td>

          <td
            class="block w-12 select-none bg-gray-50 px-2 py-0.5 text-right align-top dark:bg-slate-700"
            :class="{ 'pt-2': index === chunk.code_line_start, 'pb-2': index === chunk.code_line_end }"
          >
            {{ index }}
          </td>

          <td
            class="w-full px-2 py-0.5 align-top"
            :class="{ 'pt-2': index === chunk.code_line_start, 'pb-2': index === chunk.code_line_end }"
          >
            <!-- needed to avoid page expansion -->
            <div class="block w-0">{{ line }}</div>
          </td>
        </tr>

        <tr v-if="chunk.code.length === 0">
          <td class="p-3">
            {{
              shredded ? "Code older than 30 days is erased from Sema records for security reasons." : "Code not found"
            }}
          </td>
        </tr>
      </table>
    </div>
  </div>
</template>

<!-- This is not scoped! -->
<style>
/* HACK: kinda .. to make popovers darker */
div[class*="te-popover-"] {
  @apply text-xs dark:bg-neutral-700;
}
</style>
