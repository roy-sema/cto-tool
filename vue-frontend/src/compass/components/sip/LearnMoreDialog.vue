<script setup lang="ts">
import { Mail } from "lucide-vue-next";

defineProps<{
  product: string;
  visible: boolean;
}>();

const emit = defineEmits(["update:visible"]);

const updateVisibility = (value: boolean) => {
  emit("update:visible", value);
};
</script>

<template>
  <Dialog
    modal
    class="mx-4 lg:w-1/3"
    :visible="visible"
    :header="`Learn More About ${product}`"
    :closable="false"
    @update:visible="updateVisibility"
  >
    <p class="mb-4 text-gray-600">
      This module is coming soon. Leave your email and we'll notify you when it's available.
    </p>

    <div class="mb-4 flex items-center space-x-2">
      <Mail class="h-5 w-5 text-gray-400" />
      <a class="text-sm text-gray-500" href="mailto:info@semasoftware.com">info@semasoftware.com</a>
    </div>

    <div class="flex justify-end gap-2">
      <Button label="Close" severity="secondary" text @click="updateVisibility(false)" />
      <Button as="a" :href="`/contact?message=Learn More About ${product}`" label="Contact Us" />
    </div>
  </Dialog>
</template>
