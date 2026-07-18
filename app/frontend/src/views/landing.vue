<script setup>
  // Libs imports
  import { ref, computed, onMounted, onUnmounted } from 'vue';
  import { useRoute, useRouter } from 'vue-router';
  import {
    ApiOutlined,
    AuditOutlined,
    DesktopOutlined,
    ExclamationCircleOutlined,
    GlobalOutlined,
    LockOutlined,
    MessageOutlined,
    SafetyCertificateOutlined,
    SafetyOutlined,
    ThunderboltOutlined,
  } from '@ant-design/icons-vue';

  // Layout import
  import Default from '@/layouts/default.vue';

  // Modules imports
  import { useAuth } from '@/modules/auth';
  import { useContactModal } from '@/modules/contact';
  import { useOrganization } from '@/modules/organization';

  // Components
  import Signin from '@/components/auth/signin.vue';

  // Assets
  import orbLogo from '@/assets/img/logo.svg?url';

  // Styles
  import "@/views/landing.css";

  const route = useRoute();
  const router = useRouter();
  const auth = useAuth();
  const contactModal = useContactModal();
  const org = useOrganization();

  // Modal shown when redirected back from a failed auth attempt
  const showAuthErrorModal = computed(() => !!route.query.error);

  const closeAuthErrorModal = () => {
    router.replace({ name: 'landing' });
  };

  const showSigninModal = ref(false);

  const openSigninModal = () => {
    showSigninModal.value = true;
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

  const chatContainer = ref(null);
  const isTyping = ref(false);
  const messages = ref([]);

  const chatScenario = [
    // Step 1: User asks for stock status
    {
      type: 'user',
      textKey: 'landing.chat.step1.user',
      delay: 1500
    },
    // Step 2: Agent responds
    {
      type: 'agent',
      textKey: 'landing.chat.step2.agent',
      delay: 2000
    },
    // Step 3: Agent shows SAP table
    {
      type: 'sap-data',
      titleKey: 'landing.chat.step3.title',
      data: {
        'landing.chat.step3.material': 'landing.chat.step3.materialVal',
        'landing.chat.step3.plant': 'landing.chat.step3.plantVal',
        'landing.chat.step3.sloc': 'landing.chat.step3.slocVal',
        'landing.chat.step3.unrestricted': 'landing.chat.step3.unrestrictedVal',
        'landing.chat.step3.blocked': 'landing.chat.step3.blockedVal',
        'landing.chat.step3.reorder': 'landing.chat.step3.reorderVal',
      },
      delay: 2500
    },
    // Step 4: User creates a draft requisition
    {
      type: 'user',
      textKey: 'landing.chat.step4.user',
      delay: 2000
    },
    // Step 5: Agent processes transaction
    {
      type: 'agent',
      textKey: 'landing.chat.step5.agent',
      delay: 2000
    },
    // Step 6: Agent shows successful document creation
    {
      type: 'sap-data',
      titleKey: 'landing.chat.step6.title',
      data: {
        'landing.chat.step6.docType': 'landing.chat.step6.docTypeVal',
        'landing.chat.step6.docNumber': 'landing.chat.step6.docNumberVal',
        'landing.chat.step6.status': 'landing.chat.step6.statusVal',
        'landing.chat.step6.qty': 'landing.chat.step6.qtyVal',
        'landing.chat.step6.vendor': 'landing.chat.step6.vendorVal',
        'landing.chat.step6.value': 'landing.chat.step6.valueVal',
      },
      delay: 3500
    }
  ];

  let scenarioIndex = 0;
  let timeoutId = null;

  const scrollToBottom = () => {
    setTimeout(() => {
      if (chatContainer.value) {
        chatContainer.value.scrollTop = chatContainer.value.scrollHeight;
      }
    }, 100);
  };

  const runScenarioStep = () => {
    if (scenarioIndex >= chatScenario.length) {
      // Pause at the end and restart the loop
      timeoutId = setTimeout(() => {
        messages.value = [];
        scenarioIndex  = 0;
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

  onMounted(() => {
    runScenarioStep();
    org.load();
    window.addEventListener('auth.trigger_signin', handleSignInAction);
  });

  onUnmounted(() => {
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
              href="#features"
              class="orb-btn-secondary"
            >
              {{ $t('landing.cta.learnMore') }}
            </a>
          </div>
          <div class="orb-hero-live-scope">
            <span class="orb-hero-live-scope-dot" />
            {{ $t('landing.hero.liveScope') }}
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
                {{ $t('landing.chat.simulator.plant') }}
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
                      v-for="(valKey, labelKey) in msg.data"
                      :key="labelKey"
                    >
                      <div class="text-slate-500 text-left font-sans">
                        {{ $t(labelKey) }}:
                      </div>
                      <div class="text-slate-200 text-right truncate">
                        {{ $t(valKey) }}
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

    <!-- Features Grid Section -->
    <section
      id="features"
      class="orb-features"
    >
      <div class="orb-container">
        <h2 class="orb-features-title">
          {{ $t('landing.features.title') }}
        </h2>
        <p class="orb-features-subtitle">
          {{ $t('landing.features.subtitle') }}
        </p>

        <div class="orb-features-grid">
          <!-- Card 1: Natural Language -->
          <div class="orb-feature-card">
            <div class="orb-feature-icon">
              <MessageOutlined />
            </div>
            <h3 class="orb-feature-title">
              {{ $t('landing.features.naturalLanguage.title') }}
            </h3>
            <p class="orb-feature-desc">
              {{ $t('landing.features.naturalLanguage.desc') }}
            </p>
          </div>

          <!-- Card 2: MCP Driven -->
          <div class="orb-feature-card">
            <div class="orb-feature-icon">
              <ApiOutlined />
            </div>
            <h3 class="orb-feature-title">
              {{ $t('landing.features.mcp.title') }}
            </h3>
            <p class="orb-feature-desc">
              {{ $t('landing.features.mcp.desc') }}
            </p>
          </div>

          <!-- Card 3: Real-Time -->
          <div class="orb-feature-card">
            <div class="orb-feature-icon">
              <ThunderboltOutlined />
            </div>
            <h3 class="orb-feature-title">
              {{ $t('landing.features.realtime.title') }}
            </h3>
            <p class="orb-feature-desc">
              {{ $t('landing.features.realtime.desc') }}
            </p>
          </div>

          <!-- Card 4: Secure OAuth2 -->
          <div class="orb-feature-card">
            <div class="orb-feature-icon">
              <SafetyOutlined />
            </div>
            <h3 class="orb-feature-title">
              {{ $t('landing.features.secure.title') }}
            </h3>
            <p class="orb-feature-desc">
              {{ $t('landing.features.secure.desc') }}
            </p>
          </div>
        </div>
      </div>
    </section>

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
