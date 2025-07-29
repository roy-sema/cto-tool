<script setup lang="ts">
// This component is used to provide Vue to places in Django templates outside of the Vue app
import { getCurrentUser } from "@/common/api";
import Topbar from "@/compass/components/sip/Topbar.vue";
import UserDropdown from "@/compass/components/UserDropdown.vue";
import { useUserStore } from "@/compass/stores/user";
import { onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";

const route = useRoute();
const router = useRouter();
const userStore = useUserStore();

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

  // Allow settings even if not onboarded, as needed for connections
  const allowedPaths = ["/settings", "/contact", "/profile"];
  if (!user.organization.onboarding_completed && !allowedPaths.some((path) => route.path.startsWith(path))) {
    window.location.href = "/onboarding";
  }
};

onMounted(() => {
  loadData();

  // Allow responsiveness in the topbar
  document.getElementById("sip-topbar")?.classList.remove("min-h-24");
});
</script>

<template>
  <div>
    <Teleport to="#user-dropdown-sidebar-container">
      <UserDropdown />
    </Teleport>
    <Teleport to="#sip-topbar">
      <Topbar withMenuButton unconstrained />
    </Teleport>
  </div>
</template>
