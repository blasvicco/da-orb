<script setup>
  // Libs imports
  import { computed, h, onMounted, ref } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRouter } from 'vue-router';

  // Antd imports
  import { Switch } from 'antdv-next';
  import { ArrowLeftOutlined } from '@antdv-next/icons';

  // App modules imports
  import { useAuth } from '@/modules/auth';
  import AppAPI from '@/modules/api';

  // App components imports
  import AdminTabs from '@/components/admin/tabs.vue';
  import List from '@/components/table/list.vue';
  import PlanSummary from '@/components/admin/plan-summary.vue';
  import UserDetail from '@/components/user/detail.vue';
  import ChatLayout from '@/layouts/chat.vue';

  // App assets imports
  import orbLogo from '@/assets/img/logo.svg?url';

  import '@/views/admin/seats.css';

  const { t, te } = useI18n();
  const router = useRouter();
  const auth = useAuth();

  const actionError = ref(null);
  const allSeats = ref([]);
  const listRef = ref(null);
  const loading = ref(true);
  const planSummary = ref(null);
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

  const currentUsername = computed(() => userProfile.value.name);

  const errorLabel = (code) => (te(`errors.${code}`) ? t(`errors.${code}`) : code);

  const roleLabel = (role) => (role === 'admin' ? t('component.userDetail.roleAdmin') : t('component.userDetail.roleStandard'));

  const loadSeats = async () => {
    const result = await AppAPI.Seat.seats();
    if (!result?.errors) allSeats.value = result;
  };

  const loadPlanSummary = async () => {
    const result = await AppAPI.Usage.summary();
    if (!result?.errors) planSummary.value = result.plan;
  };

  const _runAction = async (apiCall) => {
    actionError.value = null;
    const result = await apiCall();
    if (result?.errors) {
      actionError.value = result.errors[0]?.detail || result.errors[0]?.error || 'ERROR';
      return;
    }
    await Promise.all([loadSeats(), loadPlanSummary()]);
    await listRef.value?.refresh();
  };

  const reinstate = (username) => _runAction(() => AppAPI.Seat.reinstate(username));
  const revoke = (username) => _runAction(() => AppAPI.Seat.revoke(username));
  const setRole = (username, role) => _runAction(() => AppAPI.Seat.setRole(username, role));

  // Client-side adapter: the seat endpoint returns the org's full (small, bounded-by-
  // seat_limit) seat list in one call rather than a paginated one, so filtering/sorting/
  // pagination for the generic list component happens here instead of on the server.
  const seatLoader = async ({ filters = {}, sorter = {}, limit = 20, offset = 0 }) => {
    let rows = [...allSeats.value];

    if (filters.username__icontains) {
      const needle = filters.username__icontains.toLowerCase();
      rows = rows.filter((row) => row.username.toLowerCase().includes(needle));
    }
    const roleFilter = filters.role__in || (filters.role ? [filters.role] : null);
    if (roleFilter) rows = rows.filter((row) => roleFilter.includes(row.role));
    const statusFilter = filters.status__in || (filters.status ? [filters.status] : null);
    if (statusFilter) rows = rows.filter((row) => statusFilter.includes(row.status));
    if (filters.granted_on__gte || filters.granted_on__lte) {
      rows = rows.filter((row) => {
        const value = row.granted_on?.slice(0, 10);
        if (filters.granted_on__gte && value < filters.granted_on__gte) return false;
        if (filters.granted_on__lte && value > filters.granted_on__lte) return false;
        return true;
      });
    }

    if (sorter.field) {
      const direction = sorter.order === 'descend' ? -1 : 1;
      rows.sort((a, b) => {
        if (a[sorter.field] > b[sorter.field]) return direction;
        if (a[sorter.field] < b[sorter.field]) return -direction;
        return 0;
      });
    }

    return {
      count: rows.length,
      results: rows.slice(offset, offset + limit),
    };
  };

  const columns = [
    {
      dataIndex: 'username',
      filterDropdown: true,
      key: 'username',
      sorter: true,
      title: t('admin.seats.username'),
    },
    {
      dataIndex: 'role',
      filters: [
        { text: t('component.userDetail.roleAdmin'), value: 'admin' },
        { text: t('component.userDetail.roleStandard'), value: 'standard' },
      ],
      key: 'role',
      render: (value) => roleLabel(value),
      sorter: true,
      title: t('admin.seats.role'),
      type: 'options',
    },
    {
      dataIndex: 'status',
      filters: [
        { text: t('admin.seats.statusActive'), value: 'active' },
        { text: t('admin.seats.statusRevoked'), value: 'revoked' },
      ],
      key: 'status',
      render: (_value, record) => h(
        'span',
        {
          class: [
            'orb-status-badge',
            record.status === 'active' ? 'orb-status-active' : 'orb-status-revoked',
          ],
        },
        record.status === 'active' ? t('admin.seats.statusActive') : t('admin.seats.statusRevoked'),
      ),
      sorter: true,
      title: t('admin.seats.status'),
      type: 'options',
    },
    {
      dataIndex: 'granted_on',
      filterDropdown: true,
      key: 'granted_on',
      render: (value) => new Date(value).toLocaleDateString(),
      sorter: true,
      title: t('admin.seats.grantedOn'),
      type: 'datetime',
    },
    {
      dataIndex: 'revoke',
      key: 'revoke',
      render: (_value, record) => h(Switch, {
        checked: record.status === 'active',
        checkedChildren: t('admin.seats.statusActive'),
        disabled: record.username === currentUsername.value,
        unCheckedChildren: t('admin.seats.statusRevoked'),
        onChange: (checked) => (checked ? reinstate(record.username) : revoke(record.username)),
      }),
      title: t('admin.seats.revoke'),
    },
    {
      dataIndex: 'demote',
      key: 'demote',
      render: (_value, record) => h(Switch, {
        checked: record.role === 'admin',
        disabled: record.username === currentUsername.value,
        onChange: (checked) => setRole(record.username, checked ? 'admin' : 'standard'),
      }),
      title: t('admin.seats.demote'),
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

  onMounted(async () => {
    loading.value = true;
    await Promise.all([loadSeats(), loadPlanSummary()]);
    loading.value = false;
  });
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
      <AdminTabs active="seats" />

      <h1 class="orb-admin-title">
        {{ $t('admin.seats.title') }}
      </h1>

      <div
        v-if="actionError"
        class="orb-admin-error"
      >
        {{ errorLabel(actionError) }}
      </div>

      <div
        v-if="loading"
        class="orb-admin-loading"
      >
        {{ $t('commons.loading') }}
      </div>

      <template v-else>
        <PlanSummary
          :plan="planSummary"
          variant="tag"
        />

        <List
          ref="listRef"
          :columns="columns"
          :loader="seatLoader"
        />
      </template>
    </div>
  </ChatLayout>
</template>
