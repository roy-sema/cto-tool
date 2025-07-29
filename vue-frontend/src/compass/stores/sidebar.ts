import { defineStore } from "pinia";
import { ref } from "vue";

export const useSidebarStore = defineStore("sidebar", () => {
  const expanded = ref(false);

  const collapseSidebar = (): void => {
    expanded.value = false;
  };

  const expandSidebar = (): void => {
    expanded.value = true;
  };

  return {
    expanded,
    collapseSidebar,
    expandSidebar,
  };
});
