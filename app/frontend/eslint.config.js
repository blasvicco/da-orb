import { defineConfig } from 'eslint/config';
import js from '@eslint/js';
import pluginVue from 'eslint-plugin-vue';
import css from '@eslint/css';
import globals from 'globals';
import vueParser from 'vue-eslint-parser';

export default defineConfig([
  {
    files: ['**/*.{js,ts,vue}'],
    plugins: { js },
    extends: [
      'js/recommended',
      pluginVue.configs['flat/recommended'], // Vue 3 recommended
    ],
    languageOptions: {
      globals: {
        ...globals.browser,
        __APP_ENV__: 'readonly',
      },
      parser: vueParser,  // must be the imported object
      parserOptions: {
        ecmaVersion: 'latest',
        sourceType: 'module',
      },
    },
    rules: {
      'no-unused-vars': ['error', { 
        argsIgnorePattern: '^_',   // ignore unused function arguments starting with _
        varsIgnorePattern: '^_'    // ignore unused variables starting with _
      }],
      'vue/attribute-hyphenation': 'off',
      'vue/v-on-event-hyphenation': 'off',
      'vue/multi-word-component-names': 'off', // optional
    },
  },
]);
