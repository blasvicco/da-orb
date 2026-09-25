<script setup>
  // Libs imports
  import {
    ApartmentOutlined,
    AppstoreAddOutlined,
    BarChartOutlined,
    CheckCircleFilled,
    CloseCircleFilled,
    FileExcelOutlined,
    FilePdfOutlined,
    FileSearchOutlined,
    FolderOpenOutlined,
    ProjectOutlined,
    TranslationOutlined,
  } from '@antdv-next/icons';

  // Styles
  import '@/components/landing/showcase.css';

  // Mockup sample data. Only text that changes with the locale goes through i18n;
  // file names, codes and figures are the same in every language.
  const batchRows = [
    { code: 'V10000', icon: CheckCircleFilled, status: 'created' },
    { code: 'V20000', icon: CheckCircleFilled, status: 'created' },
    { code: 'V30000', icon: CloseCircleFilled, status: 'failed' },
  ];

  // The generated file is the invoice the hero chat simulator delivers, so both tell the same story.
  const bucketFiles = [
    { icon: FileExcelOutlined, name: 'orders_q3.csv', origin: 'originUser' },
    { icon: FilePdfOutlined, nameKey: 'landing.chat.step4.file', origin: 'originWorkflow' },
  ];

  const extractionRows = ['supplier', 'date', 'qty'];

  const graphNodes = [
    { depth: 0, key: 'checkStock', status: 'completed' },
    { depth: 0, key: 'createPR', status: 'paused' },
    { depth: 1, key: 'listVendors', status: 'active' },
  ];

  const groups = [{
    id: 'work',
    items: [
      { icon: ApartmentOutlined, id: 'intentionGraph', points: 3 },
      { icon: FolderOpenOutlined, id: 'bucket', points: 3 },
      { icon: FileSearchOutlined, id: 'extraction', points: 3 },
      { icon: AppstoreAddOutlined, id: 'batch', points: 4 },
      { icon: ProjectOutlined, id: 'projects', points: 3 },
    ],
  }, {
    id: 'team',
    items: [
      { icon: TranslationOutlined, id: 'language', points: 3 },
      { icon: BarChartOutlined, id: 'usage', points: 4 },
    ],
  }];

  // Each sample is shown in its own language on purpose, so it is not localized.
  const languageSamples = [{
    agent: 'You have 3 open purchase requests.',
    code: 'EN',
    user: 'Show me the open purchase requests.',
  }, {
    agent: 'Tienes 3 solicitudes de compra abiertas.',
    code: 'ES',
    user: 'Muéstrame las solicitudes de compra abiertas.',
  }];

  const projectCards = [
    { count: 12, name: 'project.default' },
    { count: 5, name: 'landing.features.projects.mock.q4' },
    { count: 3, name: 'landing.features.projects.mock.close' },
  ];

  const usageRanks = [
    { label: 'landing.features.usage.mock.rank1', percent: 92, value: '512' },
    { label: 'landing.features.usage.mock.rank2', percent: 64, value: '356' },
    { label: 'landing.features.usage.mock.rank3', percent: 38, value: '214' },
    { label: 'admin.plan.seats', percent: 72, value: '18 / 25' },
  ];

  const usageStats = [
    { label: 'admin.usage.totalProcesses', value: '1,284' },
    { label: 'admin.usage.totalTokens', value: '4.8M' },
  ];
</script>

<template>
  <section
    id="features"
    class="orb-features orb-showcase"
  >
    <div class="orb-container">
      <h2 class="orb-features-title">
        {{ $t('landing.features.title') }}
      </h2>
      <p class="orb-features-subtitle">
        {{ $t('landing.features.subtitle') }}
      </p>

      <div
        v-for="group in groups"
        :key="group.id"
        class="orb-showcase-group"
      >
        <h3 class="orb-showcase-group-label">
          {{ $t(`landing.features.groups.${group.id}`) }}
        </h3>

        <div class="orb-showcase-rows">
          <article
            v-for="(item, index) in group.items"
            :key="item.id"
            class="orb-showcase-row"
            :class="{ 'orb-showcase-row--reverse': index % 2 === 1 }"
          >
            <!-- Text -->
            <div class="orb-showcase-text">
              <span class="orb-showcase-eyebrow">
                <component
                  :is="item.icon"
                  class="orb-showcase-eyebrow-icon"
                />
                {{ $t(`landing.features.${item.id}.eyebrow`) }}
              </span>
              <h4 class="orb-showcase-title">
                {{ $t(`landing.features.${item.id}.title`) }}
              </h4>
              <p class="orb-showcase-desc">
                {{ $t(`landing.features.${item.id}.desc`) }}
              </p>
              <ul class="orb-showcase-points">
                <li
                  v-for="point in item.points"
                  :key="point"
                  class="orb-showcase-point"
                >
                  <CheckCircleFilled class="orb-showcase-point-icon" />
                  {{ $t(`landing.features.${item.id}.points.p${point}`) }}
                </li>
              </ul>
            </div>

            <!-- Mockup (decorative, so it is hidden from assistive tech) -->
            <div
              class="orb-showcase-visual"
              aria-hidden="true"
            >
              <!-- Intention Graph -->
              <div
                v-if="item.id === 'intentionGraph'"
                class="orb-mock"
              >
                <div class="orb-mock-header">
                  <span class="orb-mock-title"><ApartmentOutlined /> {{ $t('chat.intentionGraph.title') }}</span>
                </div>
                <ul class="orb-mock-list">
                  <li
                    v-for="node in graphNodes"
                    :key="node.key"
                    class="orb-mock-node"
                    :class="[`orb-mock-node--${node.status}`, `orb-mock-node--depth-${node.depth}`]"
                  >
                    <span class="orb-mock-node-label">{{ $t(`landing.features.intentionGraph.mock.${node.key}`) }}</span>
                    <span
                      class="orb-mock-pill"
                      :class="`orb-mock-pill--${node.status}`"
                    >{{ $t(`chat.intentionGraph.status.${node.status}`) }}</span>
                  </li>
                </ul>
                <p class="orb-mock-hint">
                  ↩ {{ $t('landing.features.intentionGraph.mock.resume') }}
                </p>
              </div>

              <!-- File Bucket -->
              <div
                v-else-if="item.id === 'bucket'"
                class="orb-mock"
              >
                <div class="orb-mock-header">
                  <span class="orb-mock-title"><FolderOpenOutlined /> {{ $t('chat.bucket.title') }}</span>
                </div>
                <ul class="orb-mock-list">
                  <li
                    v-for="file in bucketFiles"
                    :key="file.origin"
                    class="orb-mock-file"
                  >
                    <component
                      :is="file.icon"
                      class="orb-mock-file-icon"
                    />
                    <span class="orb-mock-file-meta">
                      <span class="orb-mock-file-name">{{ file.nameKey ? $t(file.nameKey) : file.name }}</span>
                      <span class="orb-mock-file-origin">{{ $t(`chat.bucket.${file.origin}`) }}</span>
                    </span>
                    <span class="orb-mock-chip">{{ $t('chat.bucket.useAsContext') }}</span>
                  </li>
                </ul>
              </div>

              <!-- File content extraction -->
              <div
                v-else-if="item.id === 'extraction'"
                class="orb-mock"
              >
                <div class="orb-mock-header">
                  <span class="orb-mock-title"><FileSearchOutlined /> {{ $t('landing.features.extraction.mock.extracted') }}</span>
                  <span class="orb-mock-chip">vendor_quote.pdf</span>
                </div>
                <div class="orb-mock-kv">
                  <template
                    v-for="row in extractionRows"
                    :key="row"
                  >
                    <span class="orb-mock-kv-label">{{ $t(`landing.features.extraction.mock.${row}`) }}</span>
                    <span class="orb-mock-kv-value">{{ $t(`landing.features.extraction.mock.${row}Val`) }}</span>
                  </template>
                </div>
                <p class="orb-mock-used">
                  <CheckCircleFilled /> {{ $t('landing.features.extraction.mock.used') }}
                </p>
              </div>

              <!-- Batch processing -->
              <div
                v-else-if="item.id === 'batch'"
                class="orb-mock orb-mock--dark"
              >
                <div class="orb-mock-header">
                  <span class="orb-mock-title"><AppstoreAddOutlined /> {{ $t('landing.features.batch.mock.title') }}</span>
                </div>
                <ul class="orb-mock-list">
                  <li
                    v-for="row in batchRows"
                    :key="row.code"
                    class="orb-mock-row"
                    :class="`orb-mock-row--${row.status}`"
                  >
                    <span>{{ $t('landing.features.batch.mock.record') }} · {{ row.code }}</span>
                    <span class="orb-mock-row-status">
                      <component :is="row.icon" /> {{ $t(`landing.features.batch.mock.${row.status}`) }}
                    </span>
                  </li>
                </ul>
                <p class="orb-mock-summary">
                  {{ $t('landing.features.batch.mock.summary') }}
                </p>
              </div>

              <!-- Projects -->
              <div
                v-else-if="item.id === 'projects'"
                class="orb-mock"
              >
                <div class="orb-mock-header">
                  <span class="orb-mock-title"><ProjectOutlined /> {{ $t('project.title') }}</span>
                </div>
                <div class="orb-mock-projects">
                  <div
                    v-for="card in projectCards"
                    :key="card.name"
                    class="orb-mock-project"
                  >
                    <ProjectOutlined class="orb-mock-project-icon" />
                    <span class="orb-mock-project-name">{{ $t(card.name) }}</span>
                    <span class="orb-mock-project-count">{{ $t('landing.features.projects.mock.chats', { count: card.count }) }}</span>
                  </div>
                </div>
              </div>

              <!-- Multilanguage -->
              <div
                v-else-if="item.id === 'language'"
                class="orb-mock"
              >
                <div class="orb-mock-header">
                  <span class="orb-mock-title"><TranslationOutlined /> {{ $t('landing.features.language.mock.switch') }}</span>
                </div>
                <div
                  v-for="sample in languageSamples"
                  :key="sample.code"
                  class="orb-mock-convo"
                >
                  <span class="orb-mock-lang-code">{{ sample.code }}</span>
                  <span class="orb-mock-bubble orb-mock-bubble--user">{{ sample.user }}</span>
                  <span class="orb-mock-bubble orb-mock-bubble--agent">{{ sample.agent }}</span>
                </div>
              </div>

              <!-- Usage dashboard -->
              <div
                v-else
                class="orb-mock"
              >
                <div class="orb-mock-header">
                  <span class="orb-mock-title"><BarChartOutlined /> {{ $t('admin.usage.title') }}</span>
                </div>
                <div class="orb-mock-stats">
                  <div
                    v-for="stat in usageStats"
                    :key="stat.label"
                    class="orb-mock-stat"
                  >
                    <span class="orb-mock-stat-value">{{ stat.value }}</span>
                    <span class="orb-mock-stat-label">{{ $t(stat.label) }}</span>
                  </div>
                </div>
                <ul class="orb-mock-list">
                  <li
                    v-for="rank in usageRanks"
                    :key="rank.label"
                    class="orb-mock-rank"
                  >
                    <span class="orb-mock-rank-head">
                      <span>{{ $t(rank.label) }}</span>
                      <span class="orb-mock-rank-value">{{ rank.value }}</span>
                    </span>
                    <span class="orb-mock-bar">
                      <span
                        class="orb-mock-bar-fill"
                        :style="{ width: `${rank.percent}%` }"
                      />
                    </span>
                  </li>
                </ul>
              </div>
            </div>
          </article>
        </div>
      </div>
    </div>
  </section>
</template>
