<script setup lang="ts">
import { getCurrentUser } from "@/common/api";
import DefaultLayout from "@/compass/layouts/DefaultLayout.vue";
import { useUserStore } from "@/compass/stores/user";
import { computed, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";

const route = useRoute();
const router = useRouter();
const userStore = useUserStore();

const layout = computed(() => {
  return route.meta.layout || DefaultLayout;
});

const loadData = async () => {
  const user = await getCurrentUser();
  userStore.setInitials(user.initials);
  userStore.setFirstName(user.first_name);
  userStore.setLastName(user.last_name);
  userStore.setEmail(user.email);
  userStore.setIsStaff(user.is_staff);
  userStore.setCurrentOrganizationId(user.organization.id);
  userStore.setOnboardingCompleted(user.organization.onboarding_completed);
  userStore.setOrganizations(user.organizations);
  userStore.setProfileImage(user.profile_image);
  userStore.setProfileImageThumbnail(user.profile_image_thumbnail);
  userStore.setHideEnvironmentBanner(user.hide_environment_banner);

  const allowedPaths = ["/onboarding", "/contact", "/profile"];
  if (!user.organization.onboarding_completed && !allowedPaths.some((path) => route.path.startsWith(path))) {
    router.push({ name: "onboarding" });
  }
};

onMounted(() => {
  loadData();
});
</script>

<template>
  <component :is="layout">
    <router-view />
  </component>
</template>
