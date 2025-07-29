<script setup lang="ts">
import Footer from "@/compass/components/common/Footer.vue";
import Loading from "@/compass/components/Loading.vue";
import Sidebar from "@/compass/components/Sidebar.vue";
import Topbar from "@/compass/components/sip/Topbar.vue";
import { useSidebarStore } from "@/compass/stores/sidebar";
import { useRoute } from "vue-router";

const route = useRoute();

const sidebarStore = useSidebarStore();
</script>

<template>
  <Topbar unconstrained withMenuButton />
  <div class="sip flex h-screen flex-row overflow-hidden">
    <div class="flex-grow lg:flex lg:flex-shrink-0 lg:flex-grow-0" :class="{ hidden: !sidebarStore.expanded }">
      <Sidebar />
    </div>

    <div class="flex min-h-screen grow flex-col" :class="{ 'hidden lg:flex': sidebarStore.expanded }">
      <main
        role="main"
        class="h-full w-full flex-grow overflow-y-auto overflow-x-hidden bg-gray-50 pb-32 dark:bg-slate-800 lg:relative lg:block"
        :class="{ hidden: sidebarStore.expanded }"
      >
        <Loading v-if="!route.matched.length" />
        <router-view />
      </main>
    </div>
  </div>
  <Footer class="fixed inset-x-0 bottom-0" />
</template>
