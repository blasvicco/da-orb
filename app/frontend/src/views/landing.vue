<script setup>
  // Libs imports
  import { computed, onMounted, onUnmounted, ref } from 'vue';
  import { useRoute, useRouter } from 'vue-router';
  import {
    ApiOutlined,
    AuditOutlined,
    DesktopOutlined,
    DownloadOutlined,
    ExclamationCircleOutlined,
    GlobalOutlined,
    LockOutlined,
    MessageOutlined,
    PaperClipOutlined,
    SafetyCertificateOutlined,
    SafetyOutlined,
    ThunderboltOutlined,
  } from '@antdv-next/icons';

  // Layout import
  import Default from '@/layouts/default.vue';

  // Modules imports
  import { useAuth } from '@/modules/auth';
  import { useContactModal } from '@/modules/contact';
  import { useOrganization } from '@/modules/organization';

  // Components
  import Showcase from '@/components/landing/showcase.vue';
  import Signin from '@/components/auth/signin.vue';

  // Assets
  import orbLogo from '@/assets/img/logo.svg?url';

  // Styles
  import "@/views/landing.css";

  const auth = useAuth();
  const contactModal = useContactModal();
  const org = useOrganization();
  const route = useRoute();
  const router = useRouter();

  const chatContainer = ref(null);

  const chatScenario = [
    // Step 1: User asks for an invoice PDF
    {
      delay: 1500,
      textKey: 'landing.chat.step1.user',
      type: 'user'
    },
    // Step 2: Agent starts generating it
    {
      delay: 2000,
      textKey: 'landing.chat.step2.agent',
      type: 'agent'
    },
    // Step 3: Agent shows the invoice data (an ordered list, so the rows keep their display order)
    {
      data: [
        { label: 'landing.chat.step3.docType', value: 'landing.chat.step3.docTypeVal' },
        { label: 'landing.chat.step3.docNumber', value: 'landing.chat.step3.docNumberVal' },
        { label: 'landing.chat.step3.customer', value: 'landing.chat.step3.customerVal' },
        { label: 'landing.chat.step3.total', value: 'landing.chat.step3.totalVal' },
        { label: 'landing.chat.step3.format', value: 'landing.chat.step3.formatVal' },
      ],
      delay: 2500,
      titleKey: 'landing.chat.step3.title',
      type: 'sap-data'
    },
    // Step 4: Agent delivers the PDF, saved in the File Bucket
    {
      delay: 3500,
      fileKey: 'landing.chat.step4.file',
      textKey: 'landing.chat.step4.agent',
      type: 'agent'
    }
  ];

  const isTyping = ref(false);
  const messages = ref([]);
  let scenarioIndex = 0;

  // Modal shown when redirected back from a failed auth attempt
  const showAuthErrorModal = computed(() => !!route.query.error);

  const showSigninModal = ref(false);
  let timeoutId = null;

  const closeAuthErrorModal = () => {
    router.replace({ name: 'landing' });
  };

  const closeSigninModal = () => {
    showSigninModal.value = false;
  };

  const handleSignInAction = () => {
    if (org.hasOrganization() === false) {
      contactModal.open();
      return;
    }

    const context = org.getContext();
    if (context.auth_driver === 'open_id' || !context.auth_driver) {
      auth.signin(context);
    } else {
      openSigninModal();
    }
  };

  const openSigninModal = () => {
    showSigninModal.value = true;
  };

  const runScenarioStep = () => {
    if (scenarioIndex >= chatScenario.length) {
      // Pause at the end and restart the loop
      timeoutId = setTimeout(() => {
        messages.value = [];
        scenarioIndex = 0;
        runScenarioStep();
      }, 8000);
      return;
    }

    const step = chatScenario[scenarioIndex];

    if (step.type === 'agent' || step.type === 'sap-data') {
      isTyping.value = true;
      timeoutId = setTimeout(() => {
        isTyping.value = false;
        messages.value.push(step);
        scrollToBottom();
        scenarioIndex++;
        runScenarioStep();
      }, 1500);
    } else {
      timeoutId = setTimeout(() => {
        messages.value.push(step);
        scrollToBottom();
        scenarioIndex++;
        runScenarioStep();
      }, step.delay);
    }
  };

  const scrollToBottom = () => {
    setTimeout(() => {
      if (chatContainer.value) {
        chatContainer.value.scrollTop = chatContainer.value.scrollHeight;
      }
    }, 100);
  };

  onMounted(() => {
    runScenarioStep();
    org.load();
    window.addEventListener('auth.trigger_signin', handleSignInAction);
  });

  onUnmounted(() => {
    // v8 ignore next -- timeoutId is always assigned synchronously in onMounted first.
    if (timeoutId) clearTimeout(timeoutId);
    window.removeEventListener('auth.trigger_signin', handleSignInAction);
  });
</script>

<template>
  <Default>
    <!-- Hero Section -->
    <section class="orb-container">
      <div class="orb-hero-layout">
        <!-- Text Content -->
        <div class="orb-hero-content">
          <div class="orb-hero-badge">
            <span class="orb-hero-badge-dot" />
            {{ $t('landing.badge') }}
          </div>
          <h1 class="orb-hero-title">
            <span class="orb-hero-gradient">{{ $t('landing.hero.titleAccent') }}</span><br>
            {{ $t('landing.hero.titleRest') }}
          </h1>
          <p class="orb-hero-description">
            {{ $t('landing.description') }}
          </p>
          <div class="orb-hero-ctas">
            <button
              id="btn-hero-signin"
              class="orb-btn-primary"
              @click="handleSignInAction"
            >
              {{ org.hasOrganization() === false ? $t('landing.cta.signup') : $t('landing.cta.signin') }} ➔
            </button>
            <a
              href="#platform"
              class="orb-btn-secondary"
            >
              {{ $t('landing.cta.learnMore') }}
            </a>
          </div>
        </div>

        <!-- Interactive Chat Simulator Mockup -->
        <div class="orb-hero-preview">
          <div class="orb-chat-mock">
            <div class="orb-chat-header">
              <div class="orb-chat-agent-info">
                <img
                  :src="orbLogo"
                  class="orb-chat-avatar"
                  alt="Orb"
                >
                <div class="orb-chat-name">
                  <span>{{ $t('landing.chat.simulator.agentName') }}</span>
                  <span class="orb-chat-status">
                    <span class="orb-chat-indicator" />
                    {{ $t('landing.chat.simulator.online') }}
                  </span>
                </div>
              </div>
              <div class="text-xs font-semibold px-2.5 py-1 bg-slate-100 rounded-full text-slate-500">
                {{ $t('landing.chat.simulator.department') }}
              </div>
            </div>

            <!-- Messages Log -->
            <div
              ref="chatContainer"
              class="orb-chat-messages"
            >
              <div
                v-for="(msg, idx) in messages"
                :key="idx"
                class="orb-msg-bubble"
              >
                <!-- User Bubble -->
                <div
                  v-if="msg.type === 'user'"
                  class="orb-msg-user"
                >
                  {{ $t(msg.textKey) }}
                </div>

                <!-- Agent Bubble -->
                <div
                  v-else-if="msg.type === 'agent'"
                  class="orb-msg-agent"
                >
                  {{ $t(msg.textKey) }}
                  <!-- Generated file chip, same look as the real chat's document chip -->
                  <div
                    v-if="msg.fileKey"
                    class="orb-msg-file"
                  >
                    <PaperClipOutlined />
                    <span class="orb-msg-file-name">{{ $t(msg.fileKey) }}</span>
                    <DownloadOutlined class="orb-msg-file-download" />
                  </div>
                </div>

                <!-- SAP Data Object Bubble -->
                <div
                  v-else-if="msg.type === 'sap-data'"
                  class="orb-msg-sap-data"
                >
                  <div class="orb-msg-sap-data-header">
                    <span><DesktopOutlined /> {{ $t(msg.titleKey) }}</span>
                    <span>{{ $t('commons.success') }}</span>
                  </div>
                  <div class="grid grid-cols-2 gap-x-4 gap-y-1">
                    <template
                      v-for="row in msg.data"
                      :key="row.label"
                    >
                      <div class="text-slate-500 text-left font-sans">
                        {{ $t(row.label) }}:
                      </div>
                      <div class="text-slate-200 text-right truncate">
                        {{ $t(row.value) }}
                      </div>
                    </template>
                  </div>
                </div>
              </div>

              <!-- Typing Indicator -->
              <div
                v-if="isTyping"
                class="orb-chat-typing"
              >
                <span
                  class="orb-typing-dot"
                  style="animation-delay: 0ms"
                />
                <span
                  class="orb-typing-dot"
                  style="animation-delay: 150ms"
                />
                <span
                  class="orb-typing-dot"
                  style="animation-delay: 300ms"
                />
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- Platform Grid Section -->
    <section
      id="platform"
      class="orb-features"
    >
      <div class="orb-container">
        <h2 class="orb-features-title">
          {{ $t('landing.platform.title') }}
        </h2>
        <p class="orb-features-subtitle">
          {{ $t('landing.platform.subtitle') }}
        </p>

        <div class="orb-features-grid">
          <!-- Card 1: Natural Language -->
          <div class="orb-feature-card">
            <div class="orb-feature-icon">
              <MessageOutlined />
            </div>
            <h3 class="orb-feature-title">
              {{ $t('landing.platform.naturalLanguage.title') }}
            </h3>
            <p class="orb-feature-desc">
              {{ $t('landing.platform.naturalLanguage.desc') }}
            </p>
          </div>

          <!-- Card 2: MCP Driven -->
          <div class="orb-feature-card">
            <div class="orb-feature-icon">
              <ApiOutlined />
            </div>
            <h3 class="orb-feature-title">
              {{ $t('landing.platform.mcp.title') }}
            </h3>
            <p class="orb-feature-desc">
              {{ $t('landing.platform.mcp.desc') }}
            </p>
          </div>

          <!-- Card 3: Real-Time -->
          <div class="orb-feature-card">
            <div class="orb-feature-icon">
              <ThunderboltOutlined />
            </div>
            <h3 class="orb-feature-title">
              {{ $t('landing.platform.realtime.title') }}
            </h3>
            <p class="orb-feature-desc">
              {{ $t('landing.platform.realtime.desc') }}
            </p>
          </div>

          <!-- Card 4: Secure OAuth2 -->
          <div class="orb-feature-card">
            <div class="orb-feature-icon">
              <SafetyOutlined />
            </div>
            <h3 class="orb-feature-title">
              {{ $t('landing.platform.secure.title') }}
            </h3>
            <p class="orb-feature-desc">
              {{ $t('landing.platform.secure.desc') }}
            </p>
          </div>
        </div>
      </div>
    </section>

    <!-- Features Showcase Section -->
    <Showcase />

    <!-- Security Section -->
    <section
      id="security"
      class="orb-features"
    >
      <div class="orb-container">
        <h2 class="orb-features-title">
          {{ $t('landing.security.title') }}
        </h2>
        <p class="orb-features-subtitle">
          {{ $t('landing.security.subtitle') }}
        </p>

        <div class="orb-features-grid">
          <!-- Card 1: Private by Design -->
          <div class="orb-feature-card">
            <div class="orb-feature-icon">
              <LockOutlined />
            </div>
            <h3 class="orb-feature-title">
              {{ $t('landing.security.privateByDesign.title') }}
            </h3>
            <p class="orb-feature-desc">
              {{ $t('landing.security.privateByDesign.desc') }}
            </p>
          </div>

          <!-- Card 2: Encrypted Everywhere -->
          <div class="orb-feature-card">
            <div class="orb-feature-icon">
              <SafetyCertificateOutlined />
            </div>
            <h3 class="orb-feature-title">
              {{ $t('landing.security.encrypted.title') }}
            </h3>
            <p class="orb-feature-desc">
              {{ $t('landing.security.encrypted.desc') }}
            </p>
          </div>

          <!-- Card 3: Independently Audited -->
          <div class="orb-feature-card">
            <div class="orb-feature-icon">
              <AuditOutlined />
            </div>
            <h3 class="orb-feature-title">
              {{ $t('landing.security.audited.title') }}
            </h3>
            <p class="orb-feature-desc">
              {{ $t('landing.security.audited.desc') }}
            </p>
          </div>

          <!-- Card 4: Zero-Exposure Integrations -->
          <div class="orb-feature-card">
            <div class="orb-feature-icon">
              <GlobalOutlined />
            </div>
            <h3 class="orb-feature-title">
              {{ $t('landing.security.zeroExposure.title') }}
            </h3>
            <p class="orb-feature-desc">
              {{ $t('landing.security.zeroExposure.desc') }}
            </p>
          </div>
        </div>
      </div>
    </section>
  </Default>


  <!-- Auth failure modal — shown when redirected back with ?error= -->
  <a-modal
    id="modal-auth-error"
    :open="showAuthErrorModal"
    :footer="null"
    :closable="false"
    centered
    @cancel="closeAuthErrorModal"
  >
    <div class="orb-auth-error-modal">
      <ExclamationCircleOutlined class="orb-auth-error-icon" />
      <h3 class="orb-auth-error-title">
        {{ $t('landing.authError.title') }}
      </h3>
      <p class="orb-auth-error-desc">
        {{ $t('landing.authError.desc') }}
      </p>
      <button
        id="btn-auth-error-close"
        class="orb-btn-primary"
        @click="closeAuthErrorModal"
      >
        {{ $t('commons.close') }}
      </button>
    </div>
  </a-modal>

  <!-- Sign-in modal for credential based login -->
  <a-modal
    id="modal-signin"
    :open="showSigninModal"
    :footer="null"
    centered
    @cancel="closeSigninModal"
  >
    <Signin :context="org.getContext()" />
  </a-modal>
</template>
