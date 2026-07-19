<script setup>
  // Libs imports
  import { computed, onMounted, ref } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRouter } from 'vue-router';

  // Antd imports
  import { ArrowLeftOutlined } from '@ant-design/icons-vue';

  // App modules imports
  import { useAuth } from '@/modules/auth';
  import AppAPI from '@/modules/api';

  // App components imports
  import AdminTabs from '@/components/admin/tabs.vue';
  import RankedList from '@/components/admin/ranked-list.vue';
  import UserDetail from '@/components/user/detail.vue';
  import ChatLayout from '@/layouts/chat.vue';

  // App assets imports
  import orbLogo from '@/assets/img/logo.svg?url';

  import '@/views/admin/usage.css';

  const { t } = useI18n();
  const router = useRouter();
  const auth = useAuth();

  const loading = ref(true);
  const summary = ref(null);
  const theme = ref(localStorage.getItem('orb-theme') || 'light');

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

  // Approximated session time (updated_on - created_on summed per user) — not true
  // login duration, see the usage dashboard backend for why.
  const _formatDuration = (seconds) => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.round((seconds % 3600) / 60);
    if (hours === 0 && minutes === 0) return '<1m';
    return hours > 0 ? `${hours}h ${minutes}m` : `${minutes}m`;
  };

  const totalTokens = computed(() => (summary.value?.tokens?.total || 0).toLocaleString());
  const totalProcesses = computed(() => (summary.value?.processes?.total || 0).toLocaleString());

  const byMessages = computed(() => (summary.value?.top_users?.by_messages || []).map((row) => ({
    displayValue: row.count.toLocaleString(),
    label: row.username,
    value: row.count,
  })));

  const byProcesses = computed(() => (summary.value?.top_users?.by_processes || []).map((row) => ({
    displayValue: row.count.toLocaleString(),
    label: row.username,
    value: row.count,
  })));

  const byTokens = computed(() => (summary.value?.top_users?.by_tokens || [])
    .filter((row) => row.total_tokens)
    .map((row) => ({
      displayValue: row.total_tokens.toLocaleString(),
      label: row.username,
      value: row.total_tokens,
    })));

  const tokensByModel = computed(() => (summary.value?.tokens?.by_model || [])
    .filter((row) => row.total_tokens)
    .map((row) => ({
      displayValue: row.total_tokens.toLocaleString(),
      label: row.model_name || t('admin.usage.unknownModel'),
      value: row.total_tokens,
    })));

  const processesByType = computed(() => (summary.value?.processes?.by_process || []).map((row) => ({
    displayValue: row.count.toLocaleString(),
    label: row.process_name || t('admin.usage.unknownProcess'),
    value: row.count,
  })));

  const sessionTime = computed(() => (summary.value?.session_time || [])
    .filter((row) => row.seconds)
    .map((row) => ({
      displayValue: _formatDuration(row.seconds),
      label: row.username,
      value: row.seconds,
    })));

  const loadSummary = async () => {
    loading.value = true;
    const result = await AppAPI.Usage.summary();
    if (!result?.errors) summary.value = result;
    loading.value = false;
  };

  const toggleTheme = (isDark) => {
    theme.value = isDark ? 'dark' : 'light';
    localStorage.setItem('orb-theme', theme.value);
  };

  const handleLogout = () => {
    auth.signout();
    router.push('/');
  };

  onMounted(loadSummary);
</script>

<template>
  <ChatLayout :theme="theme">
    <template #sidebar-top>
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

      <button
        class="orb-new-chat-btn"
        @click="router.push('/chat')"
      >
        <ArrowLeftOutlined />
        {{ $t('admin.seats.backToChat') }}
      </button>
    </template>

    <template #sidebar-bottom>
      <UserDetail
        :connection="userProfile.connection"
        :name="userProfile.name"
        :role="userProfile.role"
        :initials="userInitials"
        :is-admin="true"
        :theme="theme"
        @logout="handleLogout"
        @theme-change="toggleTheme"
      />
    </template>

    <div class="orb-admin-pane">
      <AdminTabs active="usage" />

      <h1 class="orb-admin-title">
        {{ $t('admin.usage.title') }}
      </h1>

      <div
        v-if="loading"
        class="orb-admin-loading"
      >
        {{ $t('commons.loading') }}
      </div>

      <template v-else>
        <div class="orb-usage-stats">
          <div class="orb-usage-stat-tile">
            <span class="orb-usage-stat-value">{{ totalTokens }}</span>
            <span class="orb-usage-stat-label">{{ $t('admin.usage.totalTokens') }}</span>
          </div>
          <div class="orb-usage-stat-tile">
            <span class="orb-usage-stat-value">{{ totalProcesses }}</span>
            <span class="orb-usage-stat-label">{{ $t('admin.usage.totalProcesses') }}</span>
          </div>
        </div>

        <p class="orb-usage-token-note">
          {{ $t('admin.usage.tokenNote') }}
        </p>

        <div class="orb-usage-grid">
          <RankedList
            :title="$t('admin.usage.mostActiveUsers')"
            :items="byMessages"
            :empty-label="$t('admin.usage.noData')"
          />
          <RankedList
            :title="$t('admin.usage.mostTokenConsuming')"
            :items="byTokens"
            :empty-label="$t('admin.usage.noData')"
          />
          <RankedList
            :title="$t('admin.usage.mostProcessExecuting')"
            :items="byProcesses"
            :empty-label="$t('admin.usage.noData')"
          />
          <RankedList
            :title="$t('admin.usage.tokensByModel')"
            :items="tokensByModel"
            :empty-label="$t('admin.usage.noData')"
          />
          <RankedList
            :title="$t('admin.usage.processesByType')"
            :items="processesByType"
            :empty-label="$t('admin.usage.noData')"
          />
          <RankedList
            :title="$t('admin.usage.sessionTime')"
            :items="sessionTime"
            :empty-label="$t('admin.usage.noData')"
          />
        </div>
      </template>
    </div>
  </ChatLayout>
</template>
