<script setup>
  // Libs imports
  import { computed, h, ref } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { RouterLink, useRouter } from 'vue-router';

  // Antd imports
  import { ArrowLeftOutlined } from '@antdv-next/icons';

  // App modules imports
  import { useAuth } from '@/modules/auth';
  import AppAPI from '@/modules/api';
  import { useErrorText } from '@/modules/api/error-text';

  // App components imports
  import List from '@/components/table/list.vue';
  import UserDetail from '@/components/user/detail.vue';
  import ChatLayout from '@/layouts/chat.vue';

  // App assets imports
  import orbLogo from '@/assets/img/logo.svg?url';

  // The pane/title/error styles are shared with the admin views.
  import '@/views/admin/seats.css';
  import '@/views/projects.css';

  const { t } = useI18n();
  const router = useRouter();
  const auth = useAuth();
  const errorText = useErrorText();

  const editorError = ref(null);
  const editorName = ref('');
  const editorOpen = ref(false);
  const editorRecord = ref(null);
  const editorSaving = ref(false);
  const editorSummary = ref('');
  const listRef = ref(null);
  const theme = ref(localStorage.getItem('orb-theme') || 'light');

  const isDefaultRecord = computed(() => !!editorRecord.value?.is_default);

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

  // Thin passthrough: Abstract.list() and VSProject already speak the same
  // {filters, sorter, limit, offset} <-> {count, results} contract.
  const projectLoader = (opts) => AppAPI.Project.list(opts);

  const removeProject = (id) => AppAPI.Project.delete(id);

  const openEditor = (record) => {
    editorError.value = null;
    editorName.value = record?.name || '';
    editorRecord.value = record || null;
    editorSummary.value = record?.summary || '';
    editorOpen.value = true;
  };

  const closeEditor = () => {
    editorOpen.value = false;
  };

  const saveEditor = async () => {
    editorError.value = null;
    editorSaving.value = true;
    // The Default project's name is locked (the server refuses a rename too), so it is
    // never sent along with the summary.
    const payload = isDefaultRecord.value
      ? { summary: editorSummary.value }
      : { name: editorName.value, summary: editorSummary.value };
    const result = await AppAPI.Project.save(
      editorRecord.value ? { id: editorRecord.value.id, ...payload } : payload,
    );
    editorSaving.value = false;
    if (result?.errors) {
      editorError.value = errorText(result.errors[0]);
      return;
    }
    editorOpen.value = false;
    await listRef.value?.refresh();
  };

  // A project can only be deleted once it has no chats: this soft-deletes all of them.
  const emptyProject = async () => {
    editorError.value = null;
    const result = await AppAPI.Project.empty(editorRecord.value.id);
    if (result?.errors) {
      editorError.value = errorText(result.errors[0]);
      return;
    }
    editorRecord.value = { ...editorRecord.value, ...result };
    await listRef.value?.refresh();
  };

  const columns = [
    {
      dataIndex: 'name',
      filterDropdown: true,
      key: 'name',
      // The name opens the project's chats.
      render: (value, record) => h('span', [
        h(RouterLink, { to: `/projects/${record.id}` }, { default: () => value }),
        record.is_default ? ' ' : null,
        record.is_default ? h('span', { class: 'orb-status-badge orb-status-active' }, t('project.default')) : null,
      ]),
      sorter: true,
      title: t('project.columns.name'),
    },
    {
      dataIndex: 'summary',
      filterDropdown: true,
      key: 'summary',
      sorter: true,
      title: t('project.columns.summary'),
    },
    {
      dataIndex: 'chat_sessions_count',
      key: 'chat_sessions_count',
      sorter: true,
      title: t('project.columns.chatSessionsCount'),
    },
    {
      dataIndex: 'created_on',
      filterDropdown: true,
      key: 'created_on',
      render: (value) => new Date(value).toLocaleDateString(),
      sorter: true,
      title: t('project.columns.createdOn'),
      type: 'datetime',
    },
    {
      dataIndex: 'updated_on',
      filterDropdown: true,
      key: 'updated_on',
      render: (value) => new Date(value).toLocaleDateString(),
      sorter: true,
      title: t('project.columns.updatedOn'),
      type: 'datetime',
    },
    {
      dataIndex: 'accessed_on',
      filterDropdown: true,
      key: 'accessed_on',
      render: (value) => new Date(value).toLocaleDateString(),
      sorter: true,
      title: t('project.columns.accessedOn'),
      type: 'datetime',
    },
  ];

  const toggleTheme = (isDark) => {
    theme.value = isDark ? 'dark' : 'light';
    localStorage.setItem('orb-theme', theme.value);
  };

  const handleLogout = () => {
    auth.signout();
    router.push('/');
  };
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
        {{ $t('project.backToChat') }}
      </button>
    </template>

    <template #sidebar-bottom>
      <UserDetail
        :connection="userProfile.connection"
        :name="userProfile.name"
        :role="userProfile.role"
        :initials="userInitials"
        :is-admin="auth.isAdmin()"
        :theme="theme"
        @logout="handleLogout"
        @theme-change="toggleTheme"
      />
    </template>

    <div class="orb-admin-pane">
      <h1 class="orb-admin-title">
        {{ $t('project.title') }}
      </h1>

      <div class="orb-admin-actions">
        <a-button
          type="primary"
          @click="openEditor()"
        >
          {{ $t('project.newProject') }}
        </a-button>
      </div>

      <List
        ref="listRef"
        :actions="{ editor: openEditor, remover: removeProject }"
        :columns="columns"
        :loader="projectLoader"
      />
    </div>

    <a-modal
      v-model:open="editorOpen"
      :confirm-loading="editorSaving"
      :title="editorRecord ? $t('project.editTitle') : $t('project.newTitle')"
      @cancel="closeEditor"
      @ok="saveEditor"
    >
      <div class="orb-project-form">
        <div class="orb-project-form-field">
          <label class="orb-project-form-label">{{ $t('project.columns.name') }}</label>
          <a-input
            v-model:value="editorName"
            :disabled="isDefaultRecord"
          />
        </div>
        <div class="orb-project-form-field">
          <label class="orb-project-form-label">{{ $t('project.columns.summary') }}</label>
          <a-textarea
            v-model:value="editorSummary"
            :rows="3"
          />
        </div>

        <div
          v-if="editorRecord && !isDefaultRecord"
          class="orb-project-danger"
        >
          <span class="orb-project-danger-text">
            {{ $t('project.empty.description', { count: editorRecord.chat_sessions_count }) }}
          </span>
          <a-popconfirm
            :title="$t('project.empty.confirm')"
            @confirm="emptyProject"
          >
            <a-button
              danger
              :disabled="!editorRecord.chat_sessions_count"
            >
              {{ $t('project.empty.button') }}
            </a-button>
          </a-popconfirm>
        </div>

        <div
          v-if="editorError"
          class="orb-project-form-error"
        >
          {{ editorError }}
        </div>
      </div>
    </a-modal>
  </ChatLayout>
</template>
