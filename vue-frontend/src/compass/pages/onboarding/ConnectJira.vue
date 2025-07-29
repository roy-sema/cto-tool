<script setup lang="ts">
import ConnectJira from "@/compass/pages/ConnectJira.vue";
import { ArrowRightIcon } from "@heroicons/vue/24/outline";
import { useRouter } from "vue-router";

const router = useRouter();
</script>

<template>
  <div class="centered-wrapper sip my-5 flex flex-col items-center gap-5">
    <ConnectJira :isOnboarding="true" class="w-full" />
    <div>
      <Button label="Next" iconPos="right" @click="router.push({ name: 'onboarding-product-roadmap' })">
        <template #icon>
          <div class="order-1">
            <ArrowRightIcon class="size-4" />
          </div>
        </template>
      </Button>
    </div>
  </div>
</template>

<style scoped>
.centered-wrapper {
  --topbar-height: 300px;
}
</style>
