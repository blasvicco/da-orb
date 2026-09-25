<script setup>
  // Libs imports
  import { computed, h, onMounted, ref } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRouter } from 'vue-router';

  // Antd imports
  import { Button, Switch } from 'antdv-next';
  import { ArrowLeftOutlined, EyeOutlined } from '@antdv-next/icons';

  // App modules imports
  import { useAuth } from '@/modules/auth';
  import AppAPI from '@/modules/api';

  // App components imports
  import AdminTabs from '@/components/admin/tabs.vue';
  import List from '@/components/table/list.vue';
  import UserDetail from '@/components/user/detail.vue';
  import ChatLayout from '@/layouts/chat.vue';

  // App assets imports
  import orbLogo from '@/assets/img/logo.svg?url';

  import '@/views/admin/seats.css';
  import '@/views/admin/document-templates.css';

  const { t } = useI18n();
  const router = useRouter();
  const auth = useAuth();

  const DOCUMENT_TYPES = [{ label: 'Invoice', value: 'invoice' }];
  const LANGUAGES = [
    { label: t('admin.documentTemplates.languageAny'), value: '' },
    { label: 'Español', value: 'es' },
    { label: 'English', value: 'en' },
  ];

  const actionError = ref(null);
  const allTemplates = ref([]);
  const listRef = ref(null);
  const loading = ref(true);
  const theme = ref(localStorage.getItem('orb-theme') || 'light');

  const editorOpen = ref(false);
  const editorRecord = ref(null);
  const editorName = ref('');
  const editorDocumentType = ref('invoice');
  const editorBusinessPartnerRef = ref('');
  const editorLanguage = ref('');
  const editorFile = ref(null);
  const editorSaving = ref(false);

  const previewOpen = ref(false);
  const previewRecord = ref(null);
  const previewData = ref('[\n  {\n    "FieldName": "value"\n  }\n]');
  const previewError = ref(null);
  const previewLoading = ref(false);

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

  const loadTemplates = async () => {
    const result = await AppAPI.DocumentTemplate.templates();
    if (!result?.errors) allTemplates.value = result;
  };

  const _runAction = async (apiCall) => {
    actionError.value = null;
    const result = await apiCall();
    if (result?.errors) {
      actionError.value = result.errors[0]?.detail || result.errors[0]?.error || 'ERROR';
      return null;
    }
    await loadTemplates();
    await listRef.value?.refresh();
    return result;
  };

  const setDefault = (templateId) => _runAction(() => AppAPI.DocumentTemplate.setDefault(templateId));

  const removeTemplate = (templateId) => _runAction(() => AppAPI.DocumentTemplate.remove(templateId));

  // Client-side adapter, same reasoning as seats.vue's own seatLoader — an org's template
  // count is small (a handful per document type), no server-side pagination needed.
  const templateLoader = async ({ limit = 20, offset = 0 }) => ({
    count: allTemplates.value.length,
    results: allTemplates.value.slice(offset, offset + limit),
  });

  const openCreateEditor = () => {
    editorRecord.value = null;
    editorName.value = '';
    editorDocumentType.value = 'invoice';
    editorBusinessPartnerRef.value = '';
    editorLanguage.value = '';
    editorFile.value = null;
    editorOpen.value = true;
  };

  const openEditEditor = (record) => {
    editorRecord.value = record;
    editorName.value = record.name;
    editorDocumentType.value = record.document_type;
    editorBusinessPartnerRef.value = record.business_partner_ref || '';
    editorLanguage.value = record.language || '';
    editorFile.value = null;
    editorOpen.value = true;
  };

  const handleFileSelected = (event) => {
    editorFile.value = event.target.files?.[0] || null;
  };

  const closeEditor = () => {
    editorOpen.value = false;
  };

  const saveEditor = async () => {
    editorSaving.value = true;
    const overrides = {
      businessPartnerRef: editorBusinessPartnerRef.value,
      language: editorLanguage.value,
    };
    const result = editorRecord.value
      ? await AppAPI.DocumentTemplate.update(editorRecord.value.id, {
        documentType: editorDocumentType.value,
        file: editorFile.value,
        name: editorName.value,
        ...overrides,
      })
      : await AppAPI.DocumentTemplate.upload(
        editorName.value, editorDocumentType.value, editorFile.value, overrides,
      );
    editorSaving.value = false;
    if (result?.errors) {
      actionError.value = result.errors[0]?.detail || result.errors[0]?.error || 'ERROR';
      return;
    }
    editorOpen.value = false;
    await loadTemplates();
    await listRef.value?.refresh();
  };

  const openPreview = (record) => {
    previewRecord.value = record;
    previewError.value = null;
    previewOpen.value = true;
  };

  const closePreview = () => {
    previewOpen.value = false;
  };

  const runPreview = async () => {
    previewError.value = null;
    let rows;
    try {
      rows = JSON.parse(previewData.value);
    } catch {
      previewError.value = t('admin.documentTemplates.invalidSampleData');
      return;
    }
    previewLoading.value = true;
    const result = await AppAPI.DocumentTemplate.preview(previewRecord.value.id, rows);
    previewLoading.value = false;
    if (!(result instanceof Blob)) {
      previewError.value = result?.errors?.[0]?.detail || result?.errors?.[0]?.error || 'ERROR';
      return;
    }
    window.open(URL.createObjectURL(result), '_blank');
    previewOpen.value = false;
  };

  const columns = [
    {
      dataIndex: 'name',
      key: 'name',
      title: t('admin.documentTemplates.name'),
    },
    {
      dataIndex: 'document_type',
      key: 'document_type',
      title: t('admin.documentTemplates.documentType'),
    },
    {
      dataIndex: 'business_partner_ref',
      key: 'business_partner_ref',
      title: t('admin.documentTemplates.businessPartnerRef'),
    },
    {
      dataIndex: 'language',
      key: 'language',
      title: t('admin.documentTemplates.language'),
    },
    {
      dataIndex: 'is_default',
      key: 'is_default',
      // No text inside the switch itself; the label is for assistive tech only.
      render: (_value, record) => h(Switch, {
        'aria-label': record.is_default
          ? t('admin.documentTemplates.default')
          : t('admin.documentTemplates.setDefault'),
        checked: record.is_default,
        disabled: record.is_default,
        onChange: () => setDefault(record.id),
      }),
      title: t('admin.documentTemplates.default'),
    },
    {
      dataIndex: 'created_on',
      key: 'created_on',
      render: (value) => new Date(value).toLocaleDateString(),
      title: t('admin.documentTemplates.createdOn'),
    },
    {
      dataIndex: 'preview',
      key: 'preview',
      render: (_value, record) => h(
        Button,
        { onClick: () => openPreview(record), size: 'small' },
        () => h(EyeOutlined),
      ),
      title: t('admin.documentTemplates.preview'),
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
    await loadTemplates();
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
      <AdminTabs active="documentTemplates" />

      <h1 class="orb-admin-title">
        {{ $t('admin.documentTemplates.title') }}
      </h1>

      <div
        v-if="actionError"
        class="orb-admin-error"
      >
        {{ actionError }}
      </div>

      <div
        v-if="loading"
        class="orb-admin-loading"
      >
        {{ $t('commons.loading') }}
      </div>

      <template v-else>
        <div class="orb-admin-actions">
          <a-button
            type="primary"
            @click="openCreateEditor"
          >
            {{ $t('admin.documentTemplates.upload') }}
          </a-button>
        </div>

        <List
          ref="listRef"
          :columns="columns"
          :loader="templateLoader"
          :actions="{ editor: openEditEditor, remover: removeTemplate }"
        />
      </template>
    </div>

    <a-modal
      v-model:open="editorOpen"
      :title="editorRecord ? $t('admin.documentTemplates.editTitle') : $t('admin.documentTemplates.uploadTitle')"
      :confirm-loading="editorSaving"
      @ok="saveEditor"
      @cancel="closeEditor"
    >
      <div class="orb-template-form">
        <div class="orb-template-form-field">
          <label class="orb-template-form-label">{{ $t('admin.documentTemplates.name') }}</label>
          <a-input v-model:value="editorName" />
        </div>
        <div class="orb-template-form-field">
          <label class="orb-template-form-label">{{ $t('admin.documentTemplates.documentType') }}</label>
          <a-select
            v-model:value="editorDocumentType"
            :options="DOCUMENT_TYPES"
          />
        </div>
        <div class="orb-template-form-field">
          <label class="orb-template-form-label">{{ $t('admin.documentTemplates.businessPartnerRef') }}</label>
          <a-input v-model:value="editorBusinessPartnerRef" />
        </div>
        <div class="orb-template-form-field">
          <label class="orb-template-form-label">{{ $t('admin.documentTemplates.language') }}</label>
          <a-select
            v-model:value="editorLanguage"
            :options="LANGUAGES"
          />
        </div>
        <div class="orb-template-form-field">
          <label class="orb-template-form-label">{{ $t('admin.documentTemplates.file') }}</label>
          <input
            type="file"
            accept=".rpt"
            @change="handleFileSelected"
          >
        </div>
      </div>
    </a-modal>

    <a-modal
      v-model:open="previewOpen"
      :title="$t('admin.documentTemplates.previewTitle')"
      :confirm-loading="previewLoading"
      :ok-text="$t('admin.documentTemplates.renderPreview')"
      @ok="runPreview"
      @cancel="closePreview"
    >
      <p>{{ $t('admin.documentTemplates.previewHint') }}</p>
      <textarea
        v-model="previewData"
        rows="10"
        class="w-full font-mono text-sm"
      />
      <div
        v-if="previewError"
        class="orb-template-preview-error"
      >
        {{ previewError }}
      </div>
    </a-modal>
  </ChatLayout>
</template>
