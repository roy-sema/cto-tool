<script setup lang="ts">
import Footer from "@/compass/components/common/Footer.vue";
import Topbar from "@/compass/components/sip/Topbar.vue";

defineProps<{
  full?: boolean;
}>();
</script>

<template>
  <div class="sip flex min-h-screen flex-col">
    <Topbar />

    <main class="flex-grow overflow-y-auto overflow-x-hidden">
      <div class="mx-auto bg-gray-50 pb-10 dark:bg-slate-800">
        <slot>
          <router-view />
        </slot>
      </div>
    </main>

    <Footer class="fixed inset-x-0 bottom-0" />
  </div>
</template>

<style scoped>
main {
  --fixed-topbar-height: 67px;
  height: calc(100vh - var(--fixed-topbar-height));
}
</style>
