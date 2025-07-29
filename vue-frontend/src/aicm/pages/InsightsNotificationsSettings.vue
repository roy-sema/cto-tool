<script setup lang="ts">
import Teleports from "@/aicm/components/common/Teleports.vue";
import InsightsNotifications from "@/compass/components/InsightsNotifications.vue";
</script>

<template>
  <div class="sip">
    <h2 class="mb-4 text-xl font-semibold md:text-2xl">DailyMessage</h2>
    <InsightsNotifications :showContinueButton="false" />
  </div>
  <Teleports />
</template>
