<script setup>
  // Libs imports
  import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRouter } from 'vue-router';

  // Antd imports
  import { PlusOutlined } from '@ant-design/icons-vue';

  // App modules imports
  import { useAuth } from '@/modules/auth';
  import AppAPI from '@/modules/api';
  import Chat from '@/modules/websocket/chat';

  // App components imports
  import ChatBubble from '@/components/chat/bubble.vue';
  import ChatHeader from '@/components/chat/header.vue';
  import ChatHistory from '@/components/chat/history.vue';
  import ChatInput from '@/components/chat/input.vue';
  import ChatWelcome from '@/components/chat/welcome.vue';
  import UserDetail from '@/components/user/detail.vue';
  import ChatLayout from '@/layouts/chat.vue';

  // App assets imports
  import orbLogo from '@/assets/img/logo.svg?url';

  const { t, te } = useI18n();
  const router = useRouter();
  const auth = useAuth();

  // User profile sourced from real SAP session
  const userProfile = computed(() => {
    const session = auth.getSession() || {};
    return {
      name: session.user?.username || '',
      role: session.database || '',
    };
  });

  const userInitials = computed(() => {
    const name = userProfile.value.name;
    if (!name) return '?';
    const parts = name.trim().split(/\s+/);
    if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
    return name.substring(0, 2).toUpperCase();
  });

  // State Management
  const chatContainer = ref(null);
  const connectionStatus = ref('connecting');
  const isTyping = ref(false);
  const messages = ref([]);
  const promptText = ref('');
  const sessionId = ref(null);
  const sessions = ref([]);
  const statusText = ref(null);

  const chat = new Chat();

  // Theme
  const theme = ref(localStorage.getItem('orb-theme') || 'light');
  const toggleTheme = (isDark) => {
    theme.value = isDark ? 'dark' : 'light';
    localStorage.setItem('orb-theme', theme.value);
  };

  // Expertise level
  const expertiseLevel = ref(parseInt(localStorage.getItem('orb-expertise-level') || '2', 10));
  const setExpertiseLevel = (val) => {
    expertiseLevel.value = val;
    localStorage.setItem('orb-expertise-level', String(val));
  };

  // Scroll to bottom helper
  const scrollToBottom = async () => {
    await nextTick();
    if (chatContainer.value) {
      chatContainer.value.scrollTop = chatContainer.value.scrollHeight;
    }
  };

  const _timestamp = (isoString) =>
    new Date(isoString || new Date()).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  const currentSessionTitle = computed(() => {
    if (!sessionId.value) return null;
    const s = sessions.value.find((s) => s.id === sessionId.value);
    return s?.title || null;
  });

  // Reflect whether a session is still awaiting an agent reply in the sidebar list
  const setSessionPending = (id, pending) => {
    if (!id) return;
    const s = sessions.value.find((s) => s.id === id);
    if (s) s.pending = pending;
  };

  // Load and display messages for a past session, then reconnect WS to resume it
  const loadSession = async (id) => {
    messages.value = [];
    // Don't blindly clear the typing indicator — if this chat is still waiting on
    // an agent reply (per the sidebar's last-known pending state), keep showing it
    // so the user doesn't lose track of which chats are still in progress. The
    // specific status text (e.g. "Identificando proceso") isn't persisted, only
    // whether a reply is pending, so we fall back to the generic typing dots.
    isTyping.value = !!sessions.value.find((s) => s.id === id)?.pending;
    sessionId.value = id;
    statusText.value = null;
    chat.sessionId = id;
    chat.disconnect();
    setTimeout(() => chat.connect(), 300);

    const result = await AppAPI.Chat.messages(id);
    if (!result?.errors) {
      messages.value = result.map((m) => ({
        extra: m.extra || null,
        processes: m.extra?.processes || null,
        text: te(m.text) ? t(m.text) : m.text,
        time: _timestamp(m.timestamp),
        type: m.type,
      }));
      scrollToBottom();
    }
  };

  // Delete a past session and remove it from the sidebar
  const deleteSession = async (id) => {
    await AppAPI.Chat.deleteSession(id);
    sessions.value = sessions.value.filter((s) => s.id !== id);
    if (sessionId.value === id) {
      startNewChat();
    }
  };

  // Start a fresh chat — disconnect current WS (clears resume id) and reconnect
  const startNewChat = () => {
    chat.disconnect();
    chat.sessionId = null;
    isTyping.value = false;
    messages.value = [];
    sessionId.value = null;
    statusText.value = null;
    setTimeout(() => chat.connect(), 300);
  };

  // Quick prompt selection handler
  const useSuggestion = (promptKey) => {
    promptText.value = t(promptKey);
  };

  // Select a suggested process from an alert bubble
  const selectProcess = (processName) => {
    promptText.value = processName;
  };

  // Send Prompt Message Flow
  const handleSend = () => {
    if (!promptText.value.trim() || connectionStatus.value !== 'connected') return;
    chat.sendMessage(promptText.value.trim(), expertiseLevel.value);
    promptText.value = '';
  };

  // Sign out flow
  const handleLogout = () => {
    chat.disconnect();
    auth.signout();
    router.push('/');
  };

  onMounted(() => {
    chat.on('auth', (data) => {
      // session_id is only present when resuming an existing session
      if (data.session_id) {
        chat.sessionId = data.session_id;
        sessionId.value = data.session_id;
      }
    });

    chat.on('session.created', async (data) => {
      chat.sessionId = data.session_id;
      sessionId.value = data.session_id;
      // Refresh sidebar so the new session appears with its title
      const result = await AppAPI.Chat.sessions();
      if (!result?.errors) sessions.value = result;
    });

    chat.on('open', async () => {
      connectionStatus.value = 'connected';
      const result = await AppAPI.Chat.sessions();
      if (!result?.errors) sessions.value = result;
    });

    chat.on('close', () => { connectionStatus.value = 'disconnected'; });
    chat.on('error', () => { connectionStatus.value = 'disconnected'; });

    chat.onUserMessage((data) => {
      isTyping.value = true;
      messages.value.push({ text: data.text, time: _timestamp(data.time), type: 'user' });
      setSessionPending(sessionId.value, true);
      scrollToBottom();
    });

    chat.onAgentMessage((data) => {
      isTyping.value = false;
      messages.value.push({
        processes: data.processes || null,
        state: data.state || null,
        text: data.text,
        time: _timestamp(data.time),
        type: 'agent',
      });
      setSessionPending(sessionId.value, false);
      statusText.value = null;
      scrollToBottom();
    });

    chat.onSapData((data) => {
      isTyping.value = false;
      messages.value.push({ data: data.data, time: _timestamp(data.time), titleKey: data.titleKey, type: 'sap-data' });
      setSessionPending(sessionId.value, false);
      statusText.value = null;
      scrollToBottom();
    });

    chat.onSystemMessage((data) => {
      const text = te(data.text) ? t(data.text) : data.text;
      messages.value.push({ text, time: _timestamp(data.time), type: 'system' });
      scrollToBottom();
    });

    chat.onAlertMessage((data) => {
      isTyping.value = false;
      const text = te(data.text) ? t(data.text) : data.text;
      messages.value.push({
        processes: data.processes || null,
        state: data.state || null,
        text,
        time: _timestamp(data.time),
        type: 'alert',
      });
      setSessionPending(sessionId.value, false);
      statusText.value = null;
      scrollToBottom();
    });

    chat.onStatusMessage((data) => {
      // A status broadcast (e.g. "queued", or n8n's own progress pings once a
      // queued message starts firing) means something is actively in progress for
      // this chat, even if a moment earlier the previous turn's reply cleared
      // isTyping — otherwise this text would update while the indicator stays hidden.
      isTyping.value = true;
      // n8n's own progress pings are already literal translated text; Django's
      // own status notices (e.g. "queued") send an i18n key instead — translate
      // only when the value is actually a known key.
      statusText.value = (data.text && te(data.text)) ? t(data.text) : (data.text || null);
    });

    chat.connect();
  });

  onUnmounted(() => {
    chat.disconnect();
  });
</script>

<template>
  <ChatLayout :theme="theme">
    <template #sidebar-top>
      <!-- Logo -->
      <a
        href="/"
        class="orb-sidebar-logo-wrap"
      >
        <img
          :src="orbLogo"
          class="orb-sidebar-logo-icon"
          alt="Orb"
        >
        <span class="orb-sidebar-logo-text">
          {{ $t('landing.title') }}
        </span>
      </a>

      <!-- New Chat Action -->
      <button
        class="orb-new-chat-btn"
        @click="startNewChat"
      >
        <PlusOutlined />
        {{ $t('chat.sidebar.newChat') }}
      </button>

      <!-- History Ledger -->
      <ChatHistory
        :sessions="sessions"
        :active-session-id="sessionId"
        @select="loadSession"
        @delete="deleteSession"
      />
    </template>

    <template #sidebar-bottom>
      <UserDetail
        :name="userProfile.name"
        :role="userProfile.role"
        :initials="userInitials"
        :theme="theme"
        :expertise-level="expertiseLevel"
        @logout="handleLogout"
        @theme-change="toggleTheme"
        @expertise-change="setExpertiseLevel"
      />
    </template>

    <!-- Chat Pane -->
    <ChatHeader
      :session-title="currentSessionTitle"
      :has-messages="messages.length > 0"
      :connection-status="connectionStatus"
      :messages="messages"
      :user-name="userProfile.name"
    />

    <div
      ref="chatContainer"
      class="orb-chat-pane-messages"
    >
      <ChatWelcome
        v-if="messages.length === 0"
        :user-name="userProfile.name"
        @suggestion="useSuggestion"
      />
      <template v-else>
        <ChatBubble
          v-for="(msg, idx) in messages"
          :key="idx"
          :msg="msg"
          @process-select="selectProcess"
        />
      </template>

      <!-- Dynamic Typing Indicator -->
      <div
        v-if="isTyping"
        class="orb-chat-typing"
      >
        <span
          v-if="statusText"
          class="orb-typing-status"
        >{{ statusText }}</span>
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

    <ChatInput
      v-model="promptText"
      :disabled="isTyping || connectionStatus !== 'connected'"
      @send="handleSend"
    />
  </ChatLayout>
</template>

<style>
  @import "@/views/chat.css";
</style>
