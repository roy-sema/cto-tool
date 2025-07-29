<script setup lang="ts">
import PageHeader from "@/compass/components/common/PageHeader.vue";
import UploadDocuments from "@/compass/pages/UploadDocuments.vue";
</script>

<template>
  <PageHeader title="Documents" :updatedAt="null" />
  <div class="sip mx-auto mt-5 flex max-w-screen-xl flex-col gap-4 px-4">
    <UploadDocuments :isOnboarding="false" />
  </div>
</template>

<style scoped>
.centered-wrapper {
  --topbar-height: 300px;
}
</style>
