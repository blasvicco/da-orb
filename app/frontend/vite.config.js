import { fileURLToPath, URL } from 'node:url';
import { resolve, dirname } from 'node:path';
import { AntDesignVueResolver } from 'unplugin-vue-components/resolvers';
import { defineConfig } from 'vite';
import Components from 'unplugin-vue-components/vite';
import vue from '@vitejs/plugin-vue';
import VueI18nPlugin from '@intlify/unplugin-vue-i18n/vite';
import svgLoader from 'vite-svg-loader';
import tailwindcss from '@tailwindcss/vite';

// custom plugin
const dockerEnvPlugin = (options) => {
  // Expose docker contianer enviroment variables
  const exclude = options?.exclude || [];
  return {
    name: 'docker-env',
    config() {
      const env = Object.entries(process.env).reduce((env, [key, value]) => {
        if (exclude.includes(key)) return env;
        env[key] = value;
        return env;
      }, {});

      // Inject as global constant
      return {
        define: {
          __APP_ENV__: JSON.stringify(env),
        },
      };
    },
  };
}

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    Components({
      resolvers: [
        AntDesignVueResolver({
          importStyle: false, // css in js
        }),
      ],
    }),
    dockerEnvPlugin(),
    vue(),
    VueI18nPlugin({
      include: resolve(dirname(fileURLToPath(import.meta.url)), './src/i18n/locales/**'),
      runtimeOnly: false,
    }),
    svgLoader(),
    tailwindcss(),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    allowedHosts: process.env['ALLOWED_HOSTS'].split(' '),
    host: '0.0.0.0',
  },
});
