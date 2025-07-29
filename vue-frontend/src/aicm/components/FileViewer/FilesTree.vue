<script setup lang="ts">
import TWESpinner from "@/aicm/components/common/TWESpinner.vue";
import type { Node, RepositoryFile } from "@/aicm/helpers/api.d";
import { convertFilePathsToFlatTree, partition } from "@/aicm/helpers/utils";
import { DocumentIcon } from "@heroicons/vue/24/outline";
import type { Ref } from "vue";
import { computed, ref, watch } from "vue";
import treeview from "vue3-treeview";

const props = defineProps<{
  files: RepositoryFile[];
  selectedFiles: RepositoryFile[];
  selectedFilters: string[];
  expandAll?: boolean;
  loadingMoreFiles?: boolean;
}>();

const emit = defineEmits(["selectFile"]);

const openedPaths: Ref<string[]> = ref([]);
const fileTree = ref(null);
const filterText = ref("");
const preSelectedFilePath = ref("");

const FILTER_MAP = {
  ai: "chunks_ai_pure",
  blended: "chunks_ai_blended",
  human: "chunks_human",
  not_evaluated: "chunks_not_evaluated",
} as const;

type FilterKey = keyof typeof FILTER_MAP;

const chunkFilters = computed(() => {
  return props.selectedFilters.map((filter) => FILTER_MAP[filter as FilterKey]);
});

const chunksPerFile = computed(() => {
  const chunksPerFile: Record<string, number> = {};
  props.files.forEach((file: RepositoryFile) => {
    chunksPerFile[file.file_path] = chunkFilters.value.reduce((acc, filter) => acc + file[filter], 0);
  });
  return chunksPerFile;
});

const filesClean = computed(() => {
  const filesPaths = props.files.map((file) => file.file_path);
  const filteredFilesPaths = filesPaths.filter((path) =>
    // case insensitive filtering
    path.toLowerCase().includes(filterText.value.trim().toLowerCase()),
  );
  return convertFilePathsToFlatTree(filteredFilesPaths, openedPaths.value, filterText.value.trim().length > 0);
});

const numFiles = computed(() => Object.keys(props.files).length);

const config = computed(() => {
  let roots = Object.values(filesClean.value)
    .filter((file: Node) => file.root)
    .map((file: Node) => file.text);
  // directories on top, sorted alphabetically
  const filter = (x: string) => filesClean.value[x].children.length > 0;
  const [directories, files] = partition(roots, filter);
  directories.sort();
  files.sort();
  roots = [...directories, ...files];

  // TODO find better ways to display icons
  const closedIcon = {
    type: "shape",
    fill: "currentColor",
    viewBox: "0 0 16 16",
    draw: "M6.22 4.22a.75.75 0 0 1 1.06 0l3.25 3.25a.75.75 0 0 1 0 1.06l-3.25 3.25a.75.75 0 0 1-1.06-1.06L8.94 8 6.22 5.28a.75.75 0 0 1 0-1.06Z",
    class: "w-5 h-5",
  };
  const openedIcon = {
    type: "shape",
    fill: "currentColor",
    viewBox: "0 0 16 16",
    draw: "M4.22 6.22a.75.75 0 0 1 1.06 0L8 8.94l2.72-2.72a.75.75 0 1 1 1.06 1.06l-3.25 3.25a.75.75 0 0 1-1.06 0L4.22 7.28a.75.75 0 0 1 0-1.06Z",
    class: "w-5 h-5",
  };
  return { roots, openedIcon, closedIcon };
});

const getFileTreeElement = () => (fileTree?.value as any)?.$el;

const absolutePath = (path: string) => {
  return path.startsWith("/") ? path : `/${path}`;
};

// Using attribute since classes are reset by treeview component
const selectedAttr = "selected";

const markFocusedNodeAsSelected = () => {
  const fileTreeEl = getFileTreeElement();
  unmarkSelected(fileTreeEl);

  const nodeEl = fileTreeEl?.querySelector(".node-wrapper[tabindex='0']");
  if (nodeEl) nodeEl.setAttribute(selectedAttr, "true");
};

const unmarkSelected = (fileTreeEl: HTMLElement) => {
  const selected = fileTreeEl?.querySelector(`.node-wrapper[${selectedAttr}]`);
  if (selected) selected.removeAttribute(selectedAttr);
};

const nodeClicked = (node: Node) => {
  preSelectedFileUnwatch();

  if (node.children.length > 0) {
    if (openedPaths.value.includes(node.file_path)) {
      openedPaths.value = openedPaths.value.filter((path) => path !== node.file_path);
    } else {
      openedPaths.value.push(node.file_path);
    }
  } else {
    const selectedFile = props.files.find((file) => absolutePath(file.file_path) === node.file_path);
    window.location.hash = node.file_path;
    markFocusedNodeAsSelected();
    emit("selectFile", selectedFile);
  }
};

const expandTreeToPath = (filePath: string) => {
  let path = "";
  filePath.split("/").forEach((partialPath) => {
    if (!partialPath) return;
    path += `/${partialPath}`;
    openedPaths.value.push(path);
  });
};

const expandAllPaths = () => {
  openedPaths.value = Object.keys(filesClean.value).map((filePath) => `/${filePath}`);
};

const clickPreSelectedFilePath = async () => {
  // wait till the DOM is rendered
  setTimeout(() => {
    getFileTreeElement()?.querySelector(`[data-node-path="${preSelectedFilePath.value}"]`)?.parentElement?.click();
  }, 0);
};

const preSelectFirstFileInTree = () => {
  const roots = config.value.roots as string[];
  const files = roots?.filter((x: string) => filesClean.value[x].children.length == 0);
  if (files.length) preSelectedFilePath.value = `/${files[0]}`;
  else {
    const firstFile = Object.values(filesClean.value).find((a) => !a?.children.length);
    preSelectedFilePath.value = firstFile?.file_path || "";
  }
};

const preSelectedFileUnwatch = watch(filesClean, (newValue, oldValue) => {
  if (!Object.keys(newValue).length) {
    return;
  }

  const hashPath = window.location.hash.substring(2);
  if (hashPath !== "" && newValue[hashPath]?.children.length === 0) {
    preSelectedFilePath.value = `/${hashPath}`;
  } else if (props.loadingMoreFiles) {
    // wait until files are loaded
    return;
  } else {
    preSelectFirstFileInTree();
  }

  // expand tree to show the path to file
  expandTreeToPath(preSelectedFilePath.value);
  clickPreSelectedFilePath();

  // expand all paths if expandAll prop is true
  if (props.expandAll) expandAllPaths();

  preSelectedFileUnwatch();
});
</script>

<template>
  <input
    v-model="filterText"
    class="mb-2 block w-full rounded-md border-0 bg-white px-2 py-1 text-sm shadow-sm ring-1 ring-inset ring-gray-300 placeholder:text-gray-400 focus:ring-2 focus:ring-inset focus:ring-blue dark:bg-slate-600 dark:ring-slate-400 sm:text-sm sm:leading-6"
    type="text"
    placeholder="Filter files..."
  />
  <div v-if="loadingMoreFiles" class="my-2">
    <TWESpinner :size="3" />
    <div class="ml-2 inline-block text-xs opacity-80">Loading more files...</div>
  </div>
  <div v-if="numFiles > 0" class="-mr-2">
    <treeview
      ref="fileTree"
      class="w-full select-none text-xs"
      :nodes="filesClean"
      :config="config"
      @node-focus="nodeClicked"
    >
      <template #before-input="props">
        <div v-if="!props.node.children.length" :data-node-path="props.node.file_path">
          <DocumentIcon class="size-5 shrink-0 pr-1" />
        </div>
      </template>
      <template #after-input="props">
        <div v-if="!props.node.children.length" :data-node-path="props.node.file_path">
          <div class="absolute right-0 top-1/2 -translate-y-1/2 px-2">
            {{ chunksPerFile[props.node.file_path] }}
          </div>
        </div>
      </template>
    </treeview>
    <div v-if="Object.keys(filesClean).length === 0">
      <div class="mt-2 text-sm">No files found.</div>
    </div>
  </div>
  <div v-else>
    <div class="mt-2 text-sm">No files available.</div>
  </div>
</template>

<style scoped>
:deep(li) {
  @apply cursor-pointer;
}
/* TODO figure out why clicking on icon doesn't work */
:deep(.icon-wrapper) {
  @apply cursor-auto;
}
:deep(.node-wrapper) {
  @apply relative items-center rounded-l-sm py-0.5 outline-0 ring-0;
}
:deep(.node-wrapper:hover) {
  @apply bg-lightgrey dark:bg-slate-700;
}
:deep(.node-wrapper[selected]) {
  @apply border-l-4 border-blue bg-lightgrey dark:bg-slate-700;
}
:deep(.tree-level) {
  @apply w-full;
}
/* to not affect the first level */
:deep(.tree-level .tree-level) {
  @apply !pl-2;
}
:deep(.input-wrapper) {
  @apply mr-6 max-w-full overflow-hidden overflow-ellipsis whitespace-nowrap;
  overflow: hidden;
}
</style>
