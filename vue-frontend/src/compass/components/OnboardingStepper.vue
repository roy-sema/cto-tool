<script setup lang="ts">
import { useSidebarStore } from "@/compass/stores/sidebar";
import { CheckIcon } from "@heroicons/vue/24/outline";
import { computed, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

interface OnboardingStep {
  num: number;
  name: string;
  route?: string;
  subSteps?: OnboardingStep[];
  onSubStep?: OnboardingStep;
}

const route = useRoute();
const router = useRouter();
const sidebarStore = useSidebarStore();

// TODO: get this from backend
const lastCompletedStep = ref(0);

const getCurrentStep = () => {
  // Using a for loop so to allow for altered step to be returned.
  // EG adding onSubStep to the returned step. find/filter would not allow this.
  for (let step of numberedOnboardingSteps) {
    if (step.route === route.name) return step;

    const matchingSubStep = step.subSteps?.find((subStep) => subStep.route === route.name);
    if (matchingSubStep) {
      return {
        ...step,
        onSubStep: matchingSubStep,
      };
    }
  }
  return null;
};

const currentStep = computed(() => {
  const step = getCurrentStep();
  return step ? step : numberedOnboardingSteps[0];
});

const onboardingSteps = [
  {
    name: "Connect Version Control System",
    route: "onboarding-connect-vcs",
  },
  {
    name: "Connect Jira",
    route: "onboarding-connect-jira",
  },
  {
    name: "Product Roadmap",
    route: "onboarding-product-roadmap",
  },
  {
    name: "Insights Notifications",
    route: "onboarding-insights-notifications",
  },
];

const numberedOnboardingSteps: OnboardingStep[] = onboardingSteps.map((step, index) => ({ ...step, num: index + 1 }));

const canGoToStep = (step: OnboardingStep) => {
  return step.num <= currentStep.value.num || step.num <= lastCompletedStep.value;
};

const goToStep = (step: OnboardingStep) => {
  if (canGoToStep(step)) {
    sidebarStore.collapseSidebar();

    if (step.subSteps) {
      router.push({ name: step.subSteps[0].route });
      return;
    }
    router.push({ name: step.route });
  }
};

const getOnSubStepNum = (step: OnboardingStep) => {
  return step.onSubStep ? step.onSubStep.num : 0;
};
</script>

<template>
  <Stepper :value="currentStep.num">
    <StepItem v-for="step in numberedOnboardingSteps" :key="step.num" :value="step.num" @click="goToStep(step)">
      <Step asChild>
        <div class="flex items-center gap-3" :class="{ 'cursor-pointer': canGoToStep(step) }">
          <div
            class="flex size-8 shrink-0 items-center justify-center rounded-full"
            :class="{
              'bg-green-800': step.num < currentStep.num,
              'border-2 border-blue text-blue': step.num === currentStep.num,
              'border-2 text-gray-500': step.num > currentStep.num && step.num <= lastCompletedStep,
              'bg-gray-200 text-gray-500 dark:bg-slate-800': step.num > currentStep.num && step.num > lastCompletedStep,
            }"
          >
            <CheckIcon v-if="step.num < currentStep.num" class="size-4 text-white" />
            <div v-else class="text-sm font-semibold">{{ step.num }}</div>
          </div>
          <div
            :class="{
              'text-green-700': step.num < currentStep.num,
              'text-blue': step.num === currentStep.num,
              'text-gray-500': step.num > currentStep.num,
            }"
          >
            {{ step.name }}
          </div>
        </div>
        <!-- Nested Stepper -->
        <div v-if="step.num === currentStep.num && currentStep.subSteps">
          <Stepper :value="currentStep.num">
            <StepItem
              v-for="subStep in step.subSteps"
              :key="subStep.num"
              :value="subStep.num"
              @click="goToStep(subStep)"
            >
              <Step asChild>
                <div
                  class="flex items-center gap-3"
                  :class="{
                    'cursor-pointer': canGoToStep(subStep),
                  }"
                >
                  <div
                    v-if="step.num === currentStep.num && step.num !== onboardingSteps.length"
                    class="border-gr ml-4 size-3 border-b border-l"
                    :class="{
                      'border-green-800': step.num < currentStep.num || subStep.num < getOnSubStepNum(currentStep),
                      'border-blue': subStep.num === getOnSubStepNum(currentStep),
                      'border-divider-color': subStep.num > getOnSubStepNum(currentStep),
                    }"
                  />
                  <div
                    class="mt-3 flex size-6 items-center justify-center rounded-full"
                    :class="{
                      'bg-green-800': step.num < currentStep.num || subStep.num < getOnSubStepNum(currentStep),
                      'border-2 border-blue text-blue': subStep.num === getOnSubStepNum(currentStep),
                      'bg-gray-200 text-gray-500 dark:bg-slate-800': subStep.num > getOnSubStepNum(currentStep),
                    }"
                  >
                    <CheckIcon
                      v-if="step.num < currentStep.num || subStep.num < getOnSubStepNum(currentStep)"
                      class="size-4 text-white"
                    />
                    <div v-else class="text-xs font-semibold">{{ subStep.num }}</div>
                  </div>
                  <div
                    class="mt-3"
                    :class="{
                      'text-green-700': step.num < currentStep.num || subStep.num < getOnSubStepNum(currentStep),
                      'text-blue': subStep.num === getOnSubStepNum(currentStep),
                      'text-gray-500': subStep.num > getOnSubStepNum(currentStep),
                    }"
                  >
                    {{ subStep.name }}
                  </div>
                </div>
              </Step>
            </StepItem>
          </Stepper>
        </div>

        <!-- Vertical Line -->
        <div v-if="step.num !== onboardingSteps.length" class="my-1 h-6 w-8">
          <Divider layout="vertical" :class="{ complete: step.num < currentStep.num }" />
        </div>
      </Step>
    </StepItem>
  </Stepper>
</template>

<style scoped>
.complete {
  --p-divider-border-color: var(--p-green-800);
}

.border-divider-color {
  border-color: var(--p-divider-border-color);
}
</style>
