import { computed, ref } from "vue";

import { defineStore } from "pinia";

export const useUserStore = defineStore("user", () => {
  const initials = ref("");
  const email = ref("");
  const firstName = ref("");
  const lastName = ref("");
  const isStaff = ref(false);
  const currentOrganizationId = ref("");
  const onboardingCompleted = ref(false);
  const organizations = ref<Record<string, string>>({});
  const profileImage = ref<string | undefined>(undefined);
  const profileImageThumbnail = ref<string | undefined>(undefined);
  const hideEnvironmentBanner = ref(false);

  const currentOrganization = computed(() => {
    return organizations.value[currentOrganizationId.value] || "Unknown";
  });

  const setInitials = (value: string): void => {
    initials.value = value;
  };

  const setEmail = (value: string): void => {
    email.value = value;
  };

  const setFirstName = (value: string): void => {
    firstName.value = value;
  };

  const setLastName = (value: string): void => {
    lastName.value = value;
  };

  const setIsStaff = (value: boolean): void => {
    isStaff.value = value;
  };

  const setCurrentOrganizationId = (value: string): void => {
    currentOrganizationId.value = value;
  };

  const setOnboardingCompleted = (value: boolean): void => {
    onboardingCompleted.value = value;
  };

  const setOrganizations = (value: Record<string, string>): void => {
    organizations.value = value;
  };

  const setProfileImage = (value: string): void => {
    profileImage.value = value;
  };

  const setProfileImageThumbnail = (value: string): void => {
    profileImageThumbnail.value = value;
  };

  const setHideEnvironmentBanner = (value: boolean): void => {
    hideEnvironmentBanner.value = value;
  };

  return {
    initials,
    email,
    firstName,
    lastName,
    isStaff,
    currentOrganization,
    currentOrganizationId,
    organizations,
    profileImage,
    profileImageThumbnail,
    hideEnvironmentBanner,
    setInitials,
    setEmail,
    setFirstName,
    setLastName,
    setIsStaff,
    setCurrentOrganizationId,
    setOnboardingCompleted,
    setOrganizations,
    setProfileImage,
    setProfileImageThumbnail,
    setHideEnvironmentBanner,
  };
});
