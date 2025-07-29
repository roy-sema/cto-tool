<script setup lang="ts">
import type { RepositoryFileChunk } from "@/aicm/helpers/api.d";
import { ref } from "vue";
import TextButton from "./common/TextButton.vue";

const props = defineProps<{
  chunk: RepositoryFileChunk;
  attestationLabels: { [key: string]: string };
  selectedLabel: string;
}>();

const emit = defineEmits(["cancel", "submit", "update"]);
const selectedLabelMap: { [key: string]: string } = {
  blended: "human",
  ai: "human",
  human: "blended",
};

const firstLabelKey = Object.keys(props.attestationLabels)[0];
const labelField = ref(props.selectedLabel in selectedLabelMap ? selectedLabelMap[props.selectedLabel] : firstLabelKey);
const commentField = ref("");

const submit = async () => {
  emit("submit", labelField.value, commentField.value);
};

const cancel = () => {
  emit("cancel");
};
</script>

<template>
  <form class="flex items-center gap-1" @submit.prevent="submit">
    <label class="text-gray-500">Change to:</label>
    <div class="inline-block w-auto">
      <select
        v-model="labelField"
        class="block rounded-md border-0 bg-transparent px-2 py-1.5 ring-1 ring-inset ring-lightgrey placeholder:text-gray-400 dark:ring-slate-600"
      >
        <option v-for="[key, label] in Object.entries(attestationLabels)" :key="key" :value="key">
          {{ label }}
        </option>
      </select>
    </div>
    <input
      v-model="commentField"
      type="text"
      placeholder="Type comment (optional)"
      class="block w-64 rounded-md border-0 bg-transparent px-2 py-1.5 ring-1 ring-inset ring-lightgrey placeholder:text-gray-400 dark:ring-slate-600"
    />
    <button
      type="submit"
      class="inline-block rounded-md bg-blue px-3 py-1 font-semibold text-white shadow-sm hover:bg-violet focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue dark:hover:bg-pink"
    >
      Save
    </button>
    <TextButton text="Cancel" @click.prevent="cancel" />
  </form>
</template>
