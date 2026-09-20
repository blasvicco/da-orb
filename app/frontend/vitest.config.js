import { fileURLToPath, URL } from 'node:url';
import { AntdvNextResolver } from '@antdv-next/auto-import-resolver';
import { defineConfig } from 'vitest/config';
import Components from 'unplugin-vue-components/vite';
import vue from '@vitejs/plugin-vue';
import svgLoader from 'vite-svg-loader';

const stubCss = {
  name: 'stub-css',
  transform(_, id) {
    const path = id.split('?')[0];
    if (path.endsWith('.css')) {
      return { code: '', map: null };
    }
  },
};

export default defineConfig({
  plugins: [
    Components({
      resolvers: [
        AntdvNextResolver({
          resolveIcons: true,
        }),
      ],
    }),
    vue(),
    svgLoader(),
    stubCss,
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  define: {
    __APP_ENV__: JSON.stringify({
      ALLOWED_HOSTS: '',
      BASE_URL: '/',
      DEFAULT_LOCALE: 'en',
      FALLBACK_LOCALE: 'en',
      LEADS_API_URL: 'https://test.example.com/leads',
    }),
  },
  test: {
    environment: 'happy-dom',
    globals: true,
    server: {
      deps: {
        // antdv-next ships a nested dayjs whose plugin imports omit the .js
        // extension — fine for Vite's browser bundling, but Vitest's Node-based
        // SSR module resolution rejects it. Forcing this through Vite's own
        // transform (instead of Node's raw ESM resolver) sidesteps that.
        inline: [/antdv-next/, /@v-c\//],
      },
    },
    setupFiles: ['./src/tests/setup.js'],
    include: ['src/tests/**/*.test.js'],
    reporters: ['verbose'],
    onConsoleLog() {
      return false;
    },
    coverage: {
      provider: 'v8',
      reporter: ['text', 'lcov'],
      exclude: [
        'src/tests/**',
        '**/*.css',
        'src/assets/**',
        '**/*.config.js',
      ],
      thresholds: {
        branches: 100,
        functions: 100,
        lines: 100,
        statements: 100,
      },
    },
  },
});
