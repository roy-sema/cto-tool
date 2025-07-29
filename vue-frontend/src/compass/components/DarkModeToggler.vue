<script setup lang="ts">
import { ComputerDesktopIcon, MoonIcon, SunIcon } from "@heroicons/vue/24/outline";
import { computed, onMounted, ref } from "vue";

defineProps<{
  text?: true;
}>();

const localStorageKey = "color-theme";
const systemPrefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
const userPreference = ref(localStorage.getItem(localStorageKey));

const menu = ref();
const items = ref([
  {
    iconComponent: SunIcon,
    label: "Light",
    command: () => setMode("light"),
  },
  {
    iconComponent: MoonIcon,
    label: "Dark",
    command: () => setMode("dark"),
  },
  {
    iconComponent: ComputerDesktopIcon,
    label: "System",
    command: () => setMode("system"),
  },
]);

const isDarkMode = computed(() => {
  return (
    userPreference.value == "dark" || (systemPrefersDark && (!userPreference.value || userPreference.value == "system"))
  );
});

const selectedTheme = computed(() => {
  return userPreference.value === "system" ? "System" : isDarkMode.value ? "Dark" : "Light";
});

const setMode = (mode: string) => {
  localStorage.setItem(localStorageKey, mode);
  userPreference.value = mode;
  setTheme();
};

const setTheme = () => {
  if (isDarkMode.value) {
    document.documentElement.classList.add("dark");
    document.documentElement.classList.add("cc--darkmode");
  } else {
    document.documentElement.classList.remove("dark");
    document.documentElement.classList.remove("cc--darkmode");
  }
};

const toggleMenu = (event: MouseEvent) => {
  menu.value.toggle(event);
};

onMounted(() => {
  setTheme();
});
</script>

<template>
  <div>
    <Button
      size="large"
      severity="secondary"
      aria-haspopup="true"
      aria-controls="dark-mode-toggler"
      :text="text"
      @click="toggleMenu"
    >
      <template #icon>
        <SunIcon v-if="!isDarkMode" />
        <MoonIcon v-else />
      </template>
    </Button>

    <Menu id="dark-mode-toggler" ref="menu" size="small" :model="items" :popup="true">
      <template #item="{ item, props }">
        <a
          v-bind="props.action"
          class="flex w-auto items-center text-sm"
          :class="{ 'bg-cyan-50 dark:bg-slate-600': item.label === selectedTheme }"
        >
          <component :is="item.iconComponent" class="size-5" />
          <span>{{ item.label }}</span>
        </a>
      </template>
    </Menu>
  </div>
</template>
