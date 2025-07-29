<script setup lang="ts">
import { useRouter } from "vue-router";

const router = useRouter();
</script>

<template>
  <div class="centered-wrapper -mt-5">
    <div class="p-5">Onboarding goal setting second step</div>
    <Button label="Next" @click="router.push({ name: 'onboarding-connect-github' })" />
  </div>
</template>
