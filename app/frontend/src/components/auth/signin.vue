<script setup>
  // Libs imports
  import { ref } from 'vue';
  import { useRouter } from 'vue-router';
  import { ExclamationCircleOutlined, SafetyOutlined } from '@antdv-next/icons';

  // App imports
  import { useAuth } from '@/modules/auth';

  // Styles
  import '@/components/auth/signin.css';

  const props = defineProps({
    context: {
      default: () => ({}),
      type: Object,
    },
  });

  const auth = useAuth();
  const router = useRouter();

  // B1S form state (alphabetical)
  const b1sDatabase = ref('');
  const b1sError = ref(null);
  const b1sPassword = ref('');
  const b1sUsername = ref('');

  const submitB1S = async () => {
    b1sError.value = null;
    await auth.signinWithCredentials({
      database: b1sDatabase.value,
      password: b1sPassword.value,
      username: b1sUsername.value,
    });
    const error = auth.getError();
    if (error) {
      b1sError.value = error;
    } else {
      router.push({ name: 'chat' });
    }
  };
</script>

<template>
  <div class="orb-signin">
    <!-- Open ID: redirect to SAP identity provider -->
    <template v-if="props.context.auth_driver === 'open_id' || !props.context.auth_driver">
      <div class="flex flex-col gap-4 text-center items-center py-4">
        <SafetyOutlined class="text-4xl mb-2" />
        <h3 class="font-extrabold text-slate-800 text-xl tracking-tight">
          {{ $t('landing.cta.signin') }}
        </h3>
        <p class="leading-relaxed text-slate-500 text-sm max-w-sm mb-4">
          {{ $t('component.signin.description') }}
        </p>
        <button
          id="btn-sign-in-sap"
          class="orb-btn-primary w-full justify-center"
          :disabled="!props.context || auth.isLoading()"
          @click="auth.signin(props.context)"
        >
          {{ $t('landing.cta.signin') }} ➔
        </button>
      </div>
    </template>

    <!-- B1S: credential form -->
    <template v-else-if="props.context.auth_driver === 'b1s'">
      <form
        class="orb-b1s-form"
        @submit.prevent="submitB1S"
      >
        <p class="orb-b1s-form-title">
          {{ $t('landing.b1s.formTitle') }}
        </p>

        <div class="orb-b1s-field">
          <label
            class="orb-b1s-label"
            for="b1s-username"
          >
            {{ $t('landing.b1s.username') }}
          </label>
          <input
            id="b1s-username"
            v-model="b1sUsername"
            autocomplete="username"
            class="orb-b1s-input"
            required
            type="text"
            :placeholder="$t('landing.b1s.usernamePlaceholder')"
          >
        </div>

        <div class="orb-b1s-field">
          <label
            class="orb-b1s-label"
            for="b1s-password"
          >
            {{ $t('landing.b1s.password') }}
          </label>
          <input
            id="b1s-password"
            v-model="b1sPassword"
            autocomplete="current-password"
            class="orb-b1s-input"
            required
            type="password"
            :placeholder="$t('landing.b1s.passwordPlaceholder')"
          >
        </div>

        <div class="orb-b1s-field">
          <label
            class="orb-b1s-label"
            for="b1s-database"
          >
            {{ $t('landing.b1s.database') }}
          </label>
          <input
            id="b1s-database"
            v-model="b1sDatabase"
            autocomplete="off"
            class="orb-b1s-input"
            required
            type="text"
            :placeholder="$t('landing.b1s.databasePlaceholder')"
          >
        </div>

        <div
          v-if="b1sError"
          class="orb-b1s-error"
        >
          <ExclamationCircleOutlined />
          <span>{{ $te(`errors.${b1sError}`) ? $t(`errors.${b1sError}`) : b1sError }}</span>
        </div>

        <button
          id="btn-sign-in-b1s"
          class="orb-btn-primary orb-b1s-submit"
          :disabled="auth.isLoading()"
          type="submit"
        >
          {{ auth.isLoading() ? $t('landing.b1s.submitting') : $t('landing.b1s.submit') }}
        </button>
      </form>
    </template>
  </div>

  <!-- Auth loading overlay -->
  <transition name="fade">
    <div
      v-if="auth.isLoading()"
      class="orb-auth-overlay"
    >
      <div class="orb-auth-card">
        <div class="orb-auth-spinner-container">
          <div class="orb-auth-spinner" />
          <div class="orb-auth-spinner-glow" />
          <SafetyOutlined class="orb-auth-icon" />
        </div>
        <h2 class="orb-auth-title">
          {{ $t('component.signin.loadingTitle') }}
        </h2>
        <p class="orb-auth-status">
          {{ $t('component.signin.loadingDesc') }}
        </p>
      </div>
    </div>
  </transition>
</template>
