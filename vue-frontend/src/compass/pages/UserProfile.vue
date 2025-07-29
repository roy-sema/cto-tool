<script setup lang="ts">
import { updateCurrentUser } from "@/common/api";
import type { UpdateCurrentUser } from "@/common/api.d";
import { useUserStore } from "@/compass/stores/user";
import { ArrowUpTrayIcon, UserIcon } from "@heroicons/vue/24/outline";
import * as Sentry from "@sentry/vue";
import { useToast } from "primevue/usetoast";
import { ref, watchEffect } from "vue";

const userStore = useUserStore();

const toast = useToast();

const loading = ref(false);
const initials = ref("");
const firstName = ref("");
const lastName = ref("");
const email = ref("");
const profileImagePreview = ref<string | undefined>(undefined);
const profileImage = ref<File | undefined>(undefined);
const fileInput = ref<HTMLInputElement | null>(null);

watchEffect(() => {
  initials.value = userStore.initials;
  firstName.value = userStore.firstName;
  lastName.value = userStore.lastName;
  email.value = userStore.email;
  profileImagePreview.value = userStore.profileImageThumbnail;
});

const triggerFileSelect = () => {
  fileInput.value?.click();
};

const onImageSelect = (event: Event) => {
  const input = event.target as HTMLInputElement;
  const file = input.files ? input.files[0] : null;

  if (file) {
    profileImage.value = file;

    const reader = new FileReader();
    reader.onload = (e) => {
      profileImagePreview.value = e.target?.result as string;
    };
    reader.readAsDataURL(file);
  }
};

const save = async () => {
  if (!firstName.value || !lastName.value || !email.value) {
    toast.add({
      severity: "error",
      summary: "Please fill out all fields",
      life: 3000,
    });
    return;
  }

  try {
    loading.value = true;
    const data: UpdateCurrentUser = {
      first_name: firstName.value,
      last_name: lastName.value,
      email: email.value,
    };
    if (initials.value) {
      data.initials = initials.value;
    }
    if (profileImage.value) {
      data.profile_image = profileImage.value;
    }
    const response = await updateCurrentUser(data);
    toast.add({
      severity: "success",
      summary: "Profile updated",
      life: 3000,
    });
    userStore.setInitials(response.initials);
    userStore.setFirstName(response.first_name);
    userStore.setLastName(response.last_name);
    userStore.setProfileImage(response.profile_image);
    userStore.setProfileImageThumbnail(response.profile_image_thumbnail);
  } catch (error) {
    toast.add({
      severity: "error",
      summary: "There was a error updating your profile",
      life: 10000,
    });
    Sentry.captureException(error);
  } finally {
    loading.value = false;
  }
};
</script>

<template>
  <Toast />
  <div class="centered-wrapper flex flex-col">
    <div v-if="loading" class="flex items-center justify-center">
      <ProgressSpinner />
    </div>
    <div v-else>
      <div class="mb-2 ml-2 mr-auto text-xl">Profile</div>
      <Card>
        <template #content>
          <div class="flex flex-col px-8 md:flex-row md:px-0">
            <div class="mr-5 flex flex-col text-center">
              <div class="mb-5">Profile Picture</div>
              <img
                v-if="profileImagePreview"
                alt=""
                :src="profileImagePreview"
                class="m-auto h-32 w-32 cursor-pointer rounded-full object-cover"
                @click="triggerFileSelect"
              />
              <div
                v-else
                class="m-auto flex h-32 w-32 items-center justify-center rounded-full bg-gray-300 dark:bg-gray-500"
              >
                <UserIcon class="size-10 text-gray-800" />
              </div>
              <input ref="fileInput" type="file" accept="image/*" class="hidden" @change="onImageSelect" />
              <Button class="p-button-text mt-2" @click="triggerFileSelect">
                <template #default>
                  <ArrowUpTrayIcon class="size-5" />
                  <span>Upload Image</span>
                </template>
              </Button>
            </div>
            <div>
              <div class="flex flex-col gap-x-2 md:flex-row">
                <div class="flex flex-col">
                  <label for="initials" class="ml-1">Initials</label>
                  <InputText
                    id="initials"
                    v-model="initials"
                    type="text"
                    maxlength="3"
                    placeholder="Up to 3 characters"
                  />
                </div>
                <div class="flex flex-col">
                  <label for="first-name" class="ml-1">First name</label>
                  <InputText
                    id="first-name"
                    v-model="firstName"
                    type="text"
                    placeholder="Enter"
                    :invalid="!firstName"
                  />
                </div>
              </div>
              <div class="mt-2 flex flex-col">
                <label for="last-name" class="ml-1">Last name</label>
                <InputText id="last-name" v-model="lastName" type="text" placeholder="Enter" :invalid="!lastName" />
              </div>
              <div class="mt-2 flex flex-col">
                <label for="email" class="ml-1">Email</label>
                <InputText
                  id="email"
                  v-model="email"
                  type="text"
                  placeholder="Enter"
                  :disabled="true"
                  class="cursor-not-allowed"
                  :invalid="!email"
                />
              </div>
            </div>
          </div>
        </template>
        <template #footer>
          <div class="mt-2 flex w-full">
            <Button label="Save" class="ml-auto" @click="save" />
          </div>
        </template>
      </Card>
    </div>
  </div>
</template>
