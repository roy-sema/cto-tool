import js from "@eslint/js";
import typescript from "@typescript-eslint/eslint-plugin";
import typescriptParser from "@typescript-eslint/parser";
import prettier from "eslint-config-prettier";
import import_plugin from "eslint-plugin-import";
import playwright from "eslint-plugin-playwright";
import vue from "eslint-plugin-vue";
import globals from "globals";
import vueParser from "vue-eslint-parser";

const sharedGlobals = { ...globals.browser, ...globals.es2021 };

const sharedLanguageOptions = {
  ecmaVersion: "latest",
  sourceType: "module",
};

// Base TypeScript configuration
const tsBaseConfig = {
  plugins: {
    "@typescript-eslint": typescript,
    "import": import_plugin,
  },
  languageOptions: {
    ...sharedLanguageOptions,
    parser: typescriptParser,
    parserOptions: sharedLanguageOptions,
    globals: sharedGlobals,
  },
  rules: {
    ...typescript.configs.recommended.rules,
    "@typescript-eslint/no-explicit-any": "warn",
    "@typescript-eslint/consistent-type-imports": "warn",
    "@typescript-eslint/consistent-type-assertions": "error",
    "@typescript-eslint/no-unused-vars": ["warn", { argsIgnorePattern: "^_" }],
    "@typescript-eslint/no-non-null-assertion": "error",
    "@typescript-eslint/explicit-function-return-type": [
      "warn",
      {
        allowExpressions: true,
        allowTypedFunctionExpressions: true,
      },
    ],
    "@typescript-eslint/consistent-type-definitions": ["error", "interface"],
    "import/no-duplicates": "error",
  },
};

// Configurations for different file types
const configs = {
  vue: {
    files: ["**/*.vue"],
    plugins: {
      vue,
      "@typescript-eslint": typescript,
    },
    languageOptions: {
      parser: vueParser,
      parserOptions: {
        ...sharedLanguageOptions,
        parser: typescriptParser,
        extraFileExtensions: [".vue"],
      },
      globals: sharedGlobals,
    },
    rules: {
      ...vue.configs["recommended"].rules,
      "vue/multi-word-component-names": "off",
      "vue/component-api-style": ["error", ["script-setup", "composition"]],
      "vue/define-macros-order": [
        "warn",
        {
          order: ["defineProps", "defineEmits", "defineExpose", "defineSlots", "defineOptions", "defineModel"],
        },
      ],
      "vue/block-order": [
        "error",
        {
          order: ["script", "template", "style"],
        },
      ],
      "vue/component-name-in-template-casing": ["warn", "PascalCase"],
      "vue/html-self-closing": [
        "error",
        {
          html: {
            void: "always",
            normal: "always",
            component: "always",
          },
        },
      ],
      "vue/no-empty-component-block": "warn",
      "vue/no-template-target-blank": "error",
      "vue/no-unused-properties": [
        "warn",
        {
          groups: ["props", "data", "computed", "methods", "setup"],
        },
      ],
      "vue/padding-line-between-blocks": "warn",
      "vue/prefer-separate-static-class": "warn",
    },
  },

  tsTest: {
    files: ["**/__tests__/**/*.ts", "**/*.spec.ts"],
    ...tsBaseConfig,
    rules: {
      ...tsBaseConfig.rules,
      "@typescript-eslint/no-unused-vars": "warn",
      "@typescript-eslint/no-explicit-any": "off",
      "@typescript-eslint/explicit-function-return-type": "off",
    },
  },

  tsDeclaration: {
    files: ["**/*.d.ts"],
    ...tsBaseConfig,
    rules: {
      ...tsBaseConfig.rules,
      "@typescript-eslint/ban-types": "off",
      "@typescript-eslint/no-unused-vars": "off",
      "no-unused-vars": "off",
      "@typescript-eslint/no-explicit-any": "off",
      "@typescript-eslint/explicit-function-return-type": "off",
    },
  },

  tsNode: {
    files: ["*.config.*"],
    ...tsBaseConfig,
    rules: {
      ...tsBaseConfig.rules,
      "@typescript-eslint/explicit-function-return-type": "off",
    },
  },

  tsApp: {
    files: ["src/**/*.{ts,tsx}"],
    ...tsBaseConfig,
  },

  playwright: {
    files: ["e2e/**/*.{test,spec}.{js,ts,jsx,tsx}"],
    plugins: { playwright },
    rules: {
      ...playwright.configs.recommended.rules,
      "@typescript-eslint/explicit-function-return-type": "off",
    },
  },
};

export default [
  {
    ignores: [
      "**/node_modules/**",
      "**/dist/**",
      "**/.git/**",
      "**/.nuxt/**",
      "**/node_modules/.tmp/**",
      "../mvp/static/vue/**",
    ],
    linterOptions: {
      reportUnusedDisableDirectives: true,
      noInlineConfig: false,
    },
  },
  {
    files: ["**/*.{js,mjs,cjs,jsx,tsx,ts}"],
    ...js.configs.recommended,
    languageOptions: {
      ...sharedLanguageOptions,
      globals: sharedGlobals,
    },
  },
  ...Object.values(configs),
  prettier,
];
