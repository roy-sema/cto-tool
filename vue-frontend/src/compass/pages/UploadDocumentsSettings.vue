<script setup lang="ts">
import Teleports from "@/aicm/components/common/Teleports.vue";
import UploadDocuments from "@/compass/pages/UploadDocuments.vue";
</script>

<template>
  <div class="sip">
    <h2 class="mb-4 text-xl font-semibold md:text-2xl">Documents</h2>
    <UploadDocuments :isOnboarding="false" />
  </div>
  <Teleports />
</template>

<style scoped>
.centered-wrapper {
  --topbar-height: 300px;
}
</style>
