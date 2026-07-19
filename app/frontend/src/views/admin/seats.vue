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
  import UserDetail from '@/components/user/detail.vue';
  import ChatLayout from '@/layouts/chat.vue';

  // App assets imports
  import orbLogo from '@/assets/img/logo.svg?url';

  import '@/views/admin/seats.css';

  const { t, te } = useI18n();
  const router = useRouter();
  const auth = useAuth();

  const actionError = ref(null);
  const loading = ref(true);
  const seats = ref([]);
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

  const loadSeats = async () => {
    loading.value = true;
    const result = await AppAPI.Seat.seats();
    if (!result?.errors) seats.value = result;
    loading.value = false;
  };

  const errorLabel = (code) => (te(`errors.${code}`) ? t(`errors.${code}`) : code);

  const roleLabel = (role) => (role === 'admin' ? t('component.userDetail.roleAdmin') : t('component.userDetail.roleStandard'));

  const _runAction = async (apiCall) => {
    actionError.value = null;
    const result = await apiCall();
    if (result?.errors) {
      actionError.value = result.errors[0]?.detail || result.errors[0]?.error || 'ERROR';
      return;
    }
    await loadSeats();
  };

  const reinstate = (username) => _runAction(() => AppAPI.Seat.reinstate(username));
  const revoke = (username) => _runAction(() => AppAPI.Seat.revoke(username));
  const toggleRole = (seat) => _runAction(
    () => AppAPI.Seat.setRole(seat.username, seat.role === 'admin' ? 'standard' : 'admin')
  );

  const toggleTheme = (isDark) => {
    theme.value = isDark ? 'dark' : 'light';
    localStorage.setItem('orb-theme', theme.value);
  };

  const handleLogout = () => {
    auth.signout();
    router.push('/');
  };

  onMounted(loadSeats);
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

      <table
        v-else
        class="orb-admin-table"
      >
        <thead>
          <tr>
            <th>{{ $t('admin.seats.username') }}</th>
            <th>{{ $t('admin.seats.role') }}</th>
            <th>{{ $t('admin.seats.status') }}</th>
            <th>{{ $t('admin.seats.grantedOn') }}</th>
            <th>{{ $t('admin.seats.actions') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="seat in seats"
            :key="seat.id"
          >
            <td>{{ seat.username }}</td>
            <td>{{ roleLabel(seat.role) }}</td>
            <td>
              <span :class="['orb-status-badge', seat.status === 'active' ? 'orb-status-active' : 'orb-status-revoked']">
                {{ seat.status === 'active' ? $t('admin.seats.statusActive') : $t('admin.seats.statusRevoked') }}
              </span>
            </td>
            <td>{{ new Date(seat.granted_on).toLocaleDateString() }}</td>
            <td class="orb-admin-actions">
              <button
                v-if="seat.status === 'active'"
                class="orb-btn-secondary"
                @click="revoke(seat.username)"
              >
                {{ $t('admin.seats.revoke') }}
              </button>
              <button
                v-else
                class="orb-btn-secondary"
                @click="reinstate(seat.username)"
              >
                {{ $t('admin.seats.reinstate') }}
              </button>
              <button
                class="orb-btn-secondary"
                @click="toggleRole(seat)"
              >
                {{ seat.role === 'admin' ? $t('admin.seats.demote') : $t('admin.seats.promote') }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </ChatLayout>
</template>
