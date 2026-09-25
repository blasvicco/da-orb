<script setup>
  // Libs imports
  import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute, useRouter } from 'vue-router';

  // Antd imports
  import { PlusOutlined } from '@antdv-next/icons';

  // App modules imports
  import { useAuth } from '@/modules/auth';
  import AppAPI from '@/modules/api';
  import { useProject } from '@/modules/project';
  import Chat from '@/modules/websocket/chat';

  // App components imports
  import ChatBubble from '@/components/chat/bubble.vue';
  import ChatHeader from '@/components/chat/header.vue';
  import ChatHistory from '@/components/chat/history.vue';
  import ChatInput from '@/components/chat/input.vue';
  import ChatWelcome from '@/components/chat/welcome.vue';
  import ProjectSelector from '@/components/project/selector.vue';
  import RecentChats from '@/components/chat/recent-chats.vue';
  import UserDetail from '@/components/user/detail.vue';
  import ChatLayout from '@/layouts/chat.vue';

  // App assets imports
  import orbLogo from '@/assets/img/logo.svg?url';

  const { locale, t, te } = useI18n({ useScope: 'global' });
  const route = useRoute();
  const router = useRouter();
  const auth = useAuth();
  const projectStore = useProject();

  // User profile sourced from real SAP session
  const userProfile = computed(() => {
    const session = auth.getSession() || {};
    return {
      connection: session.database || '',
      name: session.user?.username || '',
      role: session.role || 'standard',
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
  const pendingContextFiles = ref([]);
  const promptText = ref('');
  const recentChatsRef = ref(null);
  const sessionId = ref(null);
  const sessions = ref([]);
  const statusText = ref(null);

  const chat = new Chat();
  // Resolvers waiting on the next 'session.created' event — see ensureSessionId().
  let sessionReadyResolvers = [];

  // Guarantees a real session_id exists, creating it ahead of any message if
  // needed (e.g. a file attached before anything is typed) — resolves
  // immediately if a session already exists, otherwise waits for the
  // 'session.created' event fired in response to chat.ensureSession().
  const ensureSessionId = () => {
    if (sessionId.value) return Promise.resolve(sessionId.value);
    return new Promise((resolve) => {
      sessionReadyResolvers.push(resolve);
      chat.ensureSession();
    });
  };

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

  const currentSessionState = computed(() => {
    if (!sessionId.value) return null;
    const s = sessions.value.find((s) => s.id === sessionId.value);
    return s?.n8n_state || null;
  });

  const currentSessionTitle = computed(() => {
    if (!sessionId.value) return null;
    const s = sessions.value.find((s) => s.id === sessionId.value);
    return s?.title || null;
  });

  const currentSessionTokens = computed(() => {
    if (!sessionId.value) return 0;
    const s = sessions.value.find((s) => s.id === sessionId.value);
    return s?.tokens_used || 0;
  });

  // Single source of truth for the sidebar session list — re-fetched rather than
  // accumulated client-side, so token totals can't drift on reconnect/replay. The list is
  // scoped to the selected project; the cross-project Recent Chats widget refreshes with it.
  const refreshSessions = async () => {
    // Not awaited: the widget is secondary, its failure must not hold up (or reject) the main list.
    recentChatsRef.value?.refresh();
    const result = await AppAPI.Chat.sessions(projectStore.currentProjectId());
    if (!result?.errors) sessions.value = result;
  };

  // Reflect whether a session is still awaiting an agent reply in the sidebar list
  const setSessionPending = (id, pending) => {
    if (!id) return;
    const s = sessions.value.find((s) => s.id === id);
    if (s) s.pending = pending;
  };

  // Reconnect shortly after a disconnect. One timer only: a second request (a quick double
  // click, or a linked chat that turns out not to exist) replaces the pending connect
  // instead of opening a second socket.
  let connectTimer = null;
  const scheduleConnect = () => {
    clearTimeout(connectTimer);
    connectTimer = setTimeout(() => chat.connect(), 300);
  };

  // Load and display messages for a past session, then reconnect WS to resume it.
  // Resolves to whether the chat's history could be loaded (false: it no longer exists).
  const loadSession = async (id) => {
    messages.value = [];
    // Don't blindly clear the typing indicator — if this chat is still waiting on
    // an agent reply (per the sidebar's last-known pending state), keep showing it
    // so the user doesn't lose track of which chats are still in progress. The
    // specific status text (e.g. "Interpretando mensaje") isn't persisted, only
    // whether a reply is pending, so we fall back to the generic typing dots.
    isTyping.value = !!sessions.value.find((s) => s.id === id)?.pending;
    pendingContextFiles.value = [];
    sessionId.value = id;
    statusText.value = null;
    chat.sessionId = id;
    chat.disconnect();
    scheduleConnect();

    const result = await AppAPI.Chat.messages(id);
    if (!result?.errors) {
      messages.value = result.map((m) => ({
        attachment: m.extra?.attachment || null,
        extra: m.extra || null,
        processes: m.extra?.processes || null,
        text: te(m.text) ? t(m.text) : m.text,
        time: _timestamp(m.timestamp),
        type: m.type,
      }));
      // The sidebar's cached `pending` flag (used above, before this fetch resolved)
      // can be stale if the agent replied while this chat was in the background —
      // trust the freshly fetched history instead: a session is only still pending
      // if its very last message is from the user.
      const last = result[result.length - 1];
      isTyping.value = !!last && last.type === 'user';
      scrollToBottom();
    }
    return !result?.errors;
  };

  // Delete a past session and remove it from the sidebar
  const deleteSession = async (id) => {
    await AppAPI.Chat.deleteSession(id);
    sessions.value = sessions.value.filter((s) => s.id !== id);
    recentChatsRef.value?.refresh();
    if (sessionId.value === id) {
      startNewChat();
    }
  };

  // Start a fresh chat — disconnect current WS (clears resume id) and reconnect
  const startNewChat = () => {
    chat.disconnect();
    // The project a brand-new chat lands in is fixed when the socket authenticates, so it
    // is (re)set here, right before every reconnect that starts a new chat.
    chat.projectId = projectStore.currentProjectId();
    chat.sessionId = null;
    isTyping.value = false;
    messages.value = [];
    pendingContextFiles.value = [];
    sessionId.value = null;
    statusText.value = null;
    scheduleConnect();
  };

  // Make a project the selected one and show its chats. Does not touch the open chat.
  const activateProject = async (id) => {
    const result = await projectStore.selectProject(id);
    if (result?.errors) return false;
    await refreshSessions();
    return true;
  };

  // Project selector: the open chat belongs to the previous project (or doesn't exist yet,
  // in which case its socket was authenticated against the previous project), so unless it
  // is also in the new project's list, leave it for a fresh chat in the new project.
  const switchProject = async (id) => {
    if (id === projectStore.currentProjectId()) return;
    if (!(await activateProject(id))) return;
    if (!sessions.value.some((s) => s.id === sessionId.value)) startNewChat();
  };

  // Recent Chats widget: may point into another project — switch to it, then open the chat.
  const openRecentChat = async ({ projectId, sessionId: id }) => {
    if (projectId !== projectStore.currentProjectId() && !(await activateProject(projectId))) return;
    await loadSession(id);
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
    chat.sendMessage(
      promptText.value.trim(),
      locale.value,
      expertiseLevel.value,
      pendingContextFiles.value.map((file) => file.id),
    );
    pendingContextFiles.value = [];
    promptText.value = '';
  };

  // Explicit click-to-navigate from the Intention Graph sidebar — switches the active
  // node immediately (resolved directly in Django, no n8n round-trip). The announcement
  // bubble is NOT pushed locally here — it's translated up front (only the frontend
  // knows the active locale) and sent along for the backend to broadcast back as a
  // 'system' message, the same round trip a typed message takes, so it lands in
  // messages.value via onSystemMessage below and gets persisted for session review.
  const handleNavigate = ({ id, label }) => {
    chat.switchActiveNode(id, t('chat.intentionGraph.contextSwitch', { label }));
  };

  // "Use as context" from the bucket panel, and/or files dropped onto the composer
  // that just finished uploading — both arm a one-shot reference that rides along
  // with the user's next message.
  const handleContextFile = (file) => {
    if (pendingContextFiles.value.some((entry) => entry.id === file.id)) return;
    pendingContextFiles.value = [...pendingContextFiles.value, file];
  };

  // Also reused as the file-deleted handler: removing a bucket file that's
  // currently selected as context clears its chip too.
  const handleRemoveContext = (fileId) => {
    pendingContextFiles.value = pendingContextFiles.value.filter((entry) => entry.id !== fileId);
  };

  // Sign out flow
  const handleLogout = () => {
    chat.disconnect();
    auth.signout();
    router.push('/');
  };

  // /chat?project=<id>&session=<id> — the links in a project's chat list — opens that chat.
  // Anything else (a missing, partial or garbled query) is just the normal Default-project start.
  const linkedChat = () => {
    const projectId = Number(route.query.project);
    const id = Number(route.query.session);
    return Number.isInteger(projectId) && projectId > 0 && Number.isInteger(id) && id > 0
      ? { projectId, sessionId: id }
      : null;
  };

  // Set on unmount so a connect still pending on the async project lookup is dropped.
  let disposed = false;

  onMounted(async () => {
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
      sessionReadyResolvers.forEach((resolve) => resolve(data.session_id));
      sessionReadyResolvers = [];
      // Refresh sidebar so the new session appears with its title
      await refreshSessions();
    });

    chat.on('open', async () => {
      connectionStatus.value = 'connected';
      await refreshSessions();
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
        attachment: data.attachment || null,
        processes: data.processes || null,
        state: data.state || null,
        text: data.text,
        time: _timestamp(data.time),
        type: 'agent',
      });
      setSessionPending(sessionId.value, false);
      statusText.value = null;
      scrollToBottom();
      refreshSessions();
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
      refreshSessions();
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

    // Every visit to the chat starts in the Default project (sign-in included); it has to
    // be known before connecting, since a new chat's project is sent with the socket's auth.
    await projectStore.loadDefault();
    if (disposed) return;
    const linked = linkedChat();
    if (linked) {
      // Consumed once, so a later reload doesn't keep re-opening this chat over wherever
      // the user has moved on to since.
      router.replace({ query: {} });
      if (await activateProject(linked.projectId)) {
        if (disposed) return;
        chat.projectId = projectStore.currentProjectId();
        // The chat may have been deleted since the link was rendered: start a fresh one in
        // that project instead of resuming something that isn't there.
        if (!(await loadSession(linked.sessionId))) startNewChat();
        return;
      }
      if (disposed) return;
    }
    chat.projectId = projectStore.currentProjectId();
    chat.connect();
  });

  onUnmounted(() => {
    disposed = true;
    clearTimeout(connectTimer);
    chat.disconnect();
  });
</script>

<template>
  <ChatLayout :theme="theme">
    <template #sidebar-top>
      <!-- Logo -->
      <div class="orb-sidebar-logo-block">
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
        <span
          v-if="userProfile.connection"
          class="orb-sidebar-connection"
        >
          {{ userProfile.connection }}
        </span>
        <span
          v-if="projectStore.currentProject()"
          class="orb-sidebar-project"
        >
          {{ projectStore.currentProject().name }}
        </span>
      </div>

      <!-- New Chat Action -->
      <button
        class="orb-new-chat-btn"
        @click="startNewChat"
      >
        <PlusOutlined />
        {{ $t('chat.sidebar.newChat') }}
      </button>

      <!-- Latest chats across every project -->
      <RecentChats
        ref="recentChatsRef"
        :active-session-id="sessionId"
        @select="openRecentChat"
      />

      <!-- Project switcher -->
      <ProjectSelector @select="switchProject" />

      <!-- History Ledger (the selected project's chats) -->
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
        :is-admin="auth.isAdmin()"
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
      :session-id="sessionId"
      :user-name="userProfile.name"
      :tokens-used="currentSessionTokens"
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
      :context-files="pendingContextFiles"
      :disabled="isTyping || connectionStatus !== 'connected'"
      :ensure-session-id="ensureSessionId"
      :messages="messages"
      :session-id="sessionId"
      :session-state="currentSessionState"
      @context-file="handleContextFile"
      @file-deleted="handleRemoveContext"
      @navigate="handleNavigate"
      @remove-context="handleRemoveContext"
      @send="handleSend"
    />
  </ChatLayout>
</template>

<style>
  @import "@/views/chat.css";
</style>
