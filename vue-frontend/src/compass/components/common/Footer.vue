<script setup lang="ts">
import SemaLogoText from "@/compass/assets/icons/sema-logo-text.svg?component";

const currentYear = new Date().getFullYear();

const tooltipText = [
  "<p>Sema publications should not be construed as legal advice on any specific facts or circumstances.</p>",
  '<p class="mt-1">The contents are intended for general information purposes only. To request reprint permission for any of our publications, please use our “Contact Us” form.</p>',
  '<p class="mt-1">The availability of this publication is not intended to create, and receipt of it does not constitute, an attorney-client relationship.</p>',
  '<p class="mt-1">The views set forth herein are the personal views of the authors and do not necessarily reflect those of the Firm.</p>',
].join("");
</script>

<template>
  <footer class="z-50 mt-auto bg-dark">
    <div class="mx-auto p-4 text-white">
      <div class="flex justify-between text-xs">
        <SemaLogoText class="w-12 lg:w-16" />
        <div class="mx-2 flex gap-5">
          <a href="/contact" class="button text-center font-semibold text-white hover:text-blue">Contact us</a>
          <a
            href="https://announcekit.co/semasoftware/release-notes/"
            target="_blank"
            rel="noopener noreferrer"
            class="button text-center font-semibold text-white hover:text-blue"
          >
            Release notes
          </a>
          <div
            v-tooltip.top="{ escape: false, value: tooltipText, pt: { text: '!w-96 !text-sm text-center' } }"
            class="button cursor-pointer text-center font-semibold text-white hover:text-blue"
          >
            Legal Disclaimer
          </div>
        </div>

        <a class="text-center" href="">&copy;{{ currentYear }} Sema</a>
      </div>
    </div>
  </footer>
</template>
