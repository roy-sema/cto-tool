<script setup lang="ts">
import DarkModeToggler from "@/compass/components/DarkModeToggler.vue";
import UserDropdown from "@/compass/components/UserDropdown.vue";
import { useSidebarStore } from "@/compass/stores/sidebar";
import { useUserStore } from "@/compass/stores/user";
import { MenuIcon } from "lucide-vue-next";
import { computed } from "vue";

defineProps<{
  unconstrained?: boolean;
  withMenuButton?: boolean;
}>();
const DJANGO_ENV = import.meta.env.VITE_DJANGO_ENV as "DEVELOPMENT" | "PRODUCTION";
const environmentColours = {
  DEVELOPMENT: "bg-green-600",
  PRODUCTION: "bg-red-600",
};

const userStore = useUserStore();

const sidebarStore = useSidebarStore();

const showEnvironmentBanner = computed(() => {
  return userStore.isStaff && !userStore.hideEnvironmentBanner;
});
</script>

<template>
  <header class="sticky top-0 z-50 bg-white shadow dark:border-slate-600 dark:bg-slate-900">
    <div
      v-if="showEnvironmentBanner"
      class="absolute left-0 right-0 top-0 z-50 text-center font-bold leading-[25px] text-white"
      :class="[environmentColours[DJANGO_ENV]]"
    >
      {{ DJANGO_ENV }}
    </div>
    <div
      class="py-4 xl:px-0"
      :class="{ 'mx-auto max-w-7xl px-4 sm:px-6': !unconstrained, 'px-2 lg:mx-6': unconstrained }"
    >
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-2">
          <button v-if="withMenuButton" id="sidebar-open" class="lg:hidden" @click="sidebarStore.expandSidebar">
            <MenuIcon />
          </button>
          <!-- Don't use <router-link> as it won't work when teleported to legacy views -->
          <a href="/" class="flex flex-col items-start gap-1 lg:gap-2">
            <h1 class="text-lg font-bold sm:text-xl lg:text-2xl">Sema Intelligence Platform</h1>
          </a>
        </div>

        <div class="flex items-center gap-1">
          <DarkModeToggler text />
          <Button as="a" href="/settings" label="Settings" size="small" severity="secondary" text />
          <div class="hidden sm:block">
            <UserDropdown text />
          </div>
        </div>
      </div>
    </div>
  </header>
</template>
