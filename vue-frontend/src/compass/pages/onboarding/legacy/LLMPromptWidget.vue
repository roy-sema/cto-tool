<script setup lang="ts">
import { useRouter } from "vue-router";

const router = useRouter();
</script>

<template>
  <div class="centered-wrapper -mt-5">
    <div class="p-5">Onboarding LLM prompt widget</div>
    <Button label="Finish" @click="router.push({ name: 'dashboard' })" />
  </div>
</template>
