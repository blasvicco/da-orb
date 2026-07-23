<script setup>
  // Libs imports
  import { computed } from 'vue';
  import { useI18n } from 'vue-i18n';

  // Style imports
  import './plan-summary.css';

  const props = defineProps({
    plan: {
      default: () => ({}),
      type: Object, // { seats: {used, total}, tokens: {used, total} }
    },
    variant: {
      default: 'tag',
      type: String, // 'tag' | 'progress'
    },
  });

  const { t } = useI18n();

  // Ant Design preset colors standing in for info/warning/error severity levels.
  const LEVEL_COLOR = { error: 'red', info: 'blue', warning: 'gold' };

  const _metric = (data) => {
    const used = data?.used || 0;
    const total = data?.total || 0;
    const remaining = Math.max(total - used, 0);
    const remainingRatio = total > 0 ? remaining / total : 1;
    let level = 'info';
    if (remainingRatio < 0.05) level = 'error';
    else if (remainingRatio < 0.25) level = 'warning';

    return {
      color: LEVEL_COLOR[level],
      label: `${used.toLocaleString()} / ${total.toLocaleString()} (${remaining.toLocaleString()})`,
      percent: total > 0 ? Math.min((used / total) * 100, 100) : 0,
    };
  };

  const seats = computed(() => _metric(props.plan?.seats));
  const tokens = computed(() => _metric(props.plan?.tokens));
</script>

<template>
  <div class="orb-plan-summary">
    <div class="orb-plan-summary-metric">
      <div class="orb-plan-summary-header">
        <span class="orb-plan-summary-label">{{ t('admin.plan.seats') }}</span>
        <a-tag
          v-if="variant === 'tag'"
          :color="seats.color"
        >
          {{ seats.label }}
        </a-tag>
        <span
          v-else
          class="orb-plan-summary-value"
        >
          {{ seats.label }}
        </span>
      </div>
      <a-progress
        v-if="variant === 'progress'"
        :percent="seats.percent"
        :show-info="false"
        :stroke-color="seats.color"
      />
    </div>

    <div class="orb-plan-summary-metric">
      <div class="orb-plan-summary-header">
        <span class="orb-plan-summary-label">{{ t('admin.plan.tokens') }}</span>
        <a-tag
          v-if="variant === 'tag'"
          :color="tokens.color"
        >
          {{ tokens.label }}
        </a-tag>
        <span
          v-else
          class="orb-plan-summary-value"
        >
          {{ tokens.label }}
        </span>
      </div>
      <a-progress
        v-if="variant === 'progress'"
        :percent="tokens.percent"
        :show-info="false"
        :stroke-color="tokens.color"
      />
    </div>
  </div>
</template>
