<script setup>
  import { useI18n } from 'vue-i18n';

  // Antd imports
  import { GlobalOutlined, PoweroffOutlined, TeamOutlined } from '@ant-design/icons-vue';

  // App components imports
  import LanguageSelector from '@/components/language/main.vue';
  import Settings from '@/components/chat/settings.vue';

  import '@/components/user/detail.css';

  defineProps({
    connection: {
      default: '',
      type: String,
    },
    expertiseLevel: {
      default: 2,
      type: Number,
    },
    initials: {
      default: '?',
      type: String,
    },
    isAdmin: {
      default: false,
      type: Boolean,
    },
    name: {
      default: '',
      type: String,
    },
    role: {
      default: 'standard',
      type: String,
    },
    theme: {
      default: 'light',
      type: String,
    },
  });

  const emit = defineEmits(['expertise-change', 'logout', 'theme-change']);

  const { t } = useI18n();
</script>

<template>
  <div class="orb-sidebar-bottom">
    <div class="orb-sidebar-lang">
      <span class="orb-sidebar-lang-label">
        <GlobalOutlined /> {{ $t('commons.language.language') }}
      </span>
      <LanguageSelector />
    </div>

    <div class="orb-user-profile">
      <div class="orb-user-details">
        <div class="orb-user-avatar">
          {{ initials }}
        </div>
        <div class="orb-user-info">
          <span class="orb-user-name">{{ name }}</span>
          <span class="orb-user-role">
            {{ role === 'admin' ? $t('component.userDetail.roleAdmin') : $t('component.userDetail.roleStandard') }}
          </span>
          <span
            v-if="connection"
            class="orb-user-connection"
            :title="$t('component.userDetail.connectedTo', { database: connection })"
          >
            {{ $t('component.userDetail.connectedTo', { database: connection }) }}
          </span>
        </div>
      </div>
      <div class="orb-user-actions">
        <Settings
          :theme="theme"
          :expertise-level="expertiseLevel"
          @theme-change="emit('theme-change', $event)"
          @expertise-change="emit('expertise-change', $event)"
        />
        <router-link
          v-if="isAdmin"
          to="/admin/seats"
          class="orb-admin-link-btn"
          :title="t('component.userDetail.adminPanel')"
        >
          <TeamOutlined />
        </router-link>
        <a-popconfirm
          :title="t('chat.sidebar.logoutConfirm')"
          :ok-text="t('commons.yes')"
          :cancel-text="t('commons.no')"
          placement="top"
          @confirm="emit('logout')"
        >
          <button
            class="orb-logout-btn"
            :title="t('chat.sidebar.logout')"
          >
            <PoweroffOutlined />
          </button>
        </a-popconfirm>
      </div>
    </div>
  </div>
</template>
