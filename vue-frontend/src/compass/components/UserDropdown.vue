<script setup lang="ts">
import { postJSON } from "@/common/api";
import { useUserStore } from "@/compass/stores/user";
import { ArrowRightStartOnRectangleIcon, ChevronDownIcon, MagnifyingGlassIcon } from "@heroicons/vue/24/outline";
// FilterService found here:
// https://github.com/primefaces/primevue/blob/b05dac3b13a9749ae6d4dc5323f72b16ed4be5c5/packages/primevue/src/listbox/Listbox.vue
import { FilterService } from "@primevue/core/api";
import { computed, getCurrentInstance, nextTick, ref } from "vue";
import { useRouter } from "vue-router";

defineProps<{
  inTopbar?: boolean;
  text?: true;
}>();

const instance = getCurrentInstance();
const uuid = ref(`user_dropdown_${instance?.uid}`);

const FILTER_THRESHOLD = 5;

const router = useRouter();
const userStore = useUserStore();

const menu = ref();
const filterInput = ref();
const filterValue = ref("");

const currentPath = computed(() => router.currentRoute.value.path);

const otherOrganizations = computed(() => {
  return Object.entries(userStore.organizations)
    .filter(([id, name]) => id !== userStore.currentOrganizationId)
    .map(([id, name]) => ({
      id,
      name,
    }));
});

const showFilter = computed(() => otherOrganizations.value.length >= FILTER_THRESHOLD);

const filteredOrganizations = computed(() => {
  if (!filterValue.value) return otherOrganizations.value;
  return FilterService.filter(otherOrganizations.value, ["name"], filterValue.value, "contains");
});

const items = computed(() => {
  if (!filteredOrganizations.value.length) {
    return [
      {
        label: "No results found",
        disabled: true,
      },
    ];
  }
  return filteredOrganizations.value.map(({ id, name }) => ({
    label: name,
    command: () => {
      window.location.href = `/change-organization/?organization_id=${id}&next=${currentPath.value}`;
    },
  }));
});

const logout = (event: MouseEvent) => {
  postJSON("/accounts/logout/", {}).then(() => {
    window.location.href = "/";
  });
};

const toggleMenu = (event: MouseEvent) => {
  menu.value.toggle(event);
  nextTick(() => {
    if (filterInput.value) {
      filterInput.value.$el.focus();
    }
  });
};
</script>

<template>
  <div>
    <Button
      size="small"
      severity="secondary"
      aria-haspopup="true"
      :aria-controls="uuid"
      :text="text"
      @click="toggleMenu"
    >
      <div class="flex items-center gap-1">
        <ProgressSpinner v-if="!userStore.email" class="!size-4" />
        <span v-else class="font-semibold">
          {{ `${userStore.firstName} ${userStore.lastName} (${userStore.currentOrganization})` }}
        </span>
      </div>
      <ChevronDownIcon class="size-3" />
    </Button>

    <Menu
      :id="uuid"
      ref="menu"
      size="small"
      class="user-dropdown"
      :class="{
        'single-organization': !otherOrganizations.length,
        'with-filter': showFilter,
        'align-topbar': inTopbar,
      }"
      :model="items"
      :popup="true"
    >
      <template #start>
        <div v-if="otherOrganizations.length" class="px-3 py-2">
          <div class="text-xs font-semibold uppercase">Switch Organization</div>

          <IconField v-if="showFilter" size="small" class="mt-2">
            <InputText
              ref="filterInput"
              v-model="filterValue"
              type="text"
              placeholder="Search"
              role="searchbox"
              autocomplete="off"
              size="small"
              class="w-full text-xs"
            />
            <InputIcon>
              <MagnifyingGlassIcon class="size-4" />
            </InputIcon>
          </IconField>
        </div>
      </template>
      <template #end>
        <a
          class="flex cursor-pointer items-center gap-2 px-3 py-2 text-sm hover:bg-gray-100 dark:hover:bg-slate-700"
          :class="{ 'border-t dark:border-slate-600': otherOrganizations.length }"
          href="/profile"
        >
          <img
            v-if="userStore.profileImageThumbnail"
            alt=""
            :src="userStore.profileImageThumbnail"
            class="h-8 w-8 rounded-full"
          />
          <div
            v-else
            class="flex h-8 w-8 items-center justify-center rounded-full bg-gray-300 text-xs dark:bg-gray-500"
          >
            <div>{{ userStore.initials }}</div>
          </div>
          <span>Profile</span>
        </a>
        <a
          class="flex cursor-pointer items-center gap-2 border-t px-3 py-2 text-sm hover:bg-gray-100 dark:border-slate-600 dark:hover:bg-slate-700"
          @click="logout"
        >
          <ArrowRightStartOnRectangleIcon class="size-4" />
          <span>Logout</span>
        </a>
      </template>
    </Menu>
  </div>
</template>

<style>
.user-dropdown.single-organization .p-menu-list {
  display: none;
}

.user-dropdown.with-filter .p-menu-list {
  @apply pt-0;
}

.user-dropdown.align-topbar {
  @apply !left-auto right-6 w-56;

  /* This fixes the 1px border difference */
  margin-right: -1px;
}

.user-dropdown .p-menu-list {
  @apply max-h-40 overflow-y-auto overflow-x-hidden text-sm;
}
</style>
