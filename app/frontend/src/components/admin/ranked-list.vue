<script setup>
  import { computed } from 'vue';

  import '@/components/admin/ranked-list.css';

  const props = defineProps({
    emptyLabel: {
      default: '',
      type: String,
    },
    items: {
      default: () => [],
      type: Array, // [{ label, value, displayValue }]
    },
    title: {
      required: true,
      type: String,
    },
  });

  const maxValue = computed(() => Math.max(1, ...props.items.map((item) => item.value)));
</script>

<template>
  <div class="orb-usage-card">
    <h3 class="orb-usage-card-title">
      {{ title }}
    </h3>
    <p
      v-if="!items.length"
      class="orb-usage-empty"
    >
      {{ emptyLabel }}
    </p>
    <ul
      v-else
      class="orb-usage-ranked-list"
    >
      <li
        v-for="item in items"
        :key="item.label"
        class="orb-usage-ranked-item"
      >
        <span class="orb-usage-ranked-label">{{ item.label }}</span>
        <div class="orb-usage-ranked-bar-track">
          <div
            class="orb-usage-ranked-bar-fill"
            :style="{ width: `${(item.value / maxValue) * 100}%` }"
          />
        </div>
        <span class="orb-usage-ranked-value">{{ item.displayValue ?? item.value }}</span>
      </li>
    </ul>
  </div>
</template>
