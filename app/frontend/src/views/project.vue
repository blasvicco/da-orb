<script setup>
  // Libs imports
  import { computed, h, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { RouterLink, useRoute, useRouter } from 'vue-router';

  // Antd imports
  import { message } from 'antdv-next';
  import { ArrowLeftOutlined, LeftOutlined } from '@antdv-next/icons';

  // App modules imports
  import { useAuth } from '@/modules/auth';
  import AppAPI from '@/modules/api';
  import { useErrorText } from '@/modules/api/error-text';

  // App components imports
  import List from '@/components/table/list.vue';
  import ProjectPicker from '@/components/project/picker.vue';
  import ProjectSelect from '@/components/project/select.vue';
  import UserDetail from '@/components/user/detail.vue';
  import ChatLayout from '@/layouts/chat.vue';

  // App assets imports
  import orbLogo from '@/assets/img/logo.svg?url';

  // The pane/title/error/action-row styles are shared with the other list pages.
  import '@/views/admin/seats.css';
  import '@/views/project.css';

  const { t } = useI18n();
  const route = useRoute();
  const router = useRouter();
  const auth = useAuth();
  const errorText = useErrorText();

  const listRef = ref(null);
  const moving = ref(false);
  const notFound = ref(false);
  const project = ref(null);
  const selectedKeys = ref([]);
  const theme = ref(localStorage.getItem('orb-theme') || 'light');

  const projectId = computed(() => Number(route.params.id));

  const moveLabel = computed(() => (selectedKeys.value.length
    ? t('project.view.moveCount', { count: selectedKeys.value.length })
    : t('project.view.move')));

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

  // Which rows are ticked lives here (not in the table), so it survives paging.
  const rowSelection = computed(() => ({
    onChange: (keys) => { selectedKeys.value = keys; },
    preserveSelectedRowKeys: true,
    selectedRowKeys: selectedKeys.value,
  }));

  const loadProject = async (id) => {
    notFound.value = false;
    project.value = null;
    // A garbled id (/projects/abc) can never exist: say so without asking the server.
    if (!Number.isInteger(id)) {
      notFound.value = true;
      return;
    }
    const result = await AppAPI.Project.get(id);
    // A newer navigation may have replaced this one while the request was in flight.
    if (id !== projectId.value) return;
    if (result?.errors) {
      notFound.value = true;
      return;
    }
    project.value = result;
  };

  // Thin passthrough plus the project filter: Abstract.list() and VSChatSession already
  // speak the same {filters, sorter, limit, offset} <-> {count, results} contract.
  const chatLoader = (opts) => AppAPI.ChatSession.list({
    ...opts,
    filters: { ...opts.filters, project_id: projectId.value },
  });

  const goToProject = (id) => {
    if (id !== projectId.value) router.push({ name: 'project', params: { id } });
  };

  const moveSelected = async (targetId) => {
    moving.value = true;
    const result = await AppAPI.ChatSession.move(selectedKeys.value, targetId);
    moving.value = false;
    if (result?.errors) {
      message.error(errorText(result.errors[0]));
      // The list on screen is stale (a chat or the project is gone): show what's really there.
      if (result.errors[0]?.code === 'not_found') {
        selectedKeys.value = [];
        await listRef.value?.refresh();
      }
      return;
    }
    message.success(t('project.view.moved', { count: result.moved }, result.moved));
    selectedKeys.value = [];
    await listRef.value?.refresh();
  };

  const columns = [
    {
      dataIndex: 'title',
      filterDropdown: true,
      key: 'title',
      // Opens the chat itself: the chat view resumes it, in its project.
      render: (value, record) => h(
        RouterLink,
        { to: { name: 'chat', query: { project: record.project, session: record.id } } },
        { default: () => value || t('chat.sidebar.history.untitled') },
      ),
      sorter: true,
      title: t('project.view.columns.title'),
    },
    {
      dataIndex: 'tokens_used',
      key: 'tokens_used',
      render: (value) => Number(value).toLocaleString(),
      sorter: true,
      title: t('project.view.columns.tokensUsed'),
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
  ];

  const toggleTheme = (isDark) => {
    theme.value = isDark ? 'dark' : 'light';
    localStorage.setItem('orb-theme', theme.value);
  };

  const handleLogout = () => {
    auth.signout();
    router.push('/');
  };

  // Loads on entry and whenever the dropdown (or a link) switches project.
  watch(projectId, (id) => {
    selectedKeys.value = [];
    loadProject(id);
  }, { immediate: true });
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
      <router-link
        class="orb-project-back"
        to="/projects"
      >
        <LeftOutlined />
        {{ $t('project.view.backToProjects') }}
      </router-link>

      <div
        v-if="notFound"
        class="orb-admin-error"
      >
        {{ $t('project.view.notFound') }}
      </div>

      <template v-else-if="project">
        <h1 class="orb-admin-title">
          {{ project.name }}
        </h1>

        <div class="orb-admin-actions">
          <div class="orb-project-switcher">
            <span class="orb-project-switcher-label">
              {{ $t('project.view.switchProject') }}
            </span>
            <div class="orb-project-switcher-select">
              <ProjectSelect
                :current="project"
                @select="goToProject"
              />
            </div>
          </div>

          <ProjectPicker
            :exclude-id="project.id"
            @select="moveSelected"
          >
            <a-button
              :disabled="!selectedKeys.length"
              :loading="moving"
              type="primary"
            >
              {{ moveLabel }}
            </a-button>
          </ProjectPicker>
        </div>

        <List
          :key="projectId"
          ref="listRef"
          :columns="columns"
          :loader="chatLoader"
          :row-selection="rowSelection"
        />
      </template>

      <div
        v-else
        class="orb-admin-loading"
      >
        {{ $t('commons.loading') }}
      </div>
    </div>
  </ChatLayout>
</template>
