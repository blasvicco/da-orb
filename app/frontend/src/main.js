// Lib imports
import { createApp } from 'vue';
import { createPinia } from 'pinia';

// App imports
import App from '@/app.vue';
import i18n from '@/i18n';
import router from '@/router';

// Style imports
import "@/styles/main.css";

createApp(App)
  .use(router)
  .use(createPinia())
  .use(i18n)
  .mount('#app');
