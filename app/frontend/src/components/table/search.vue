<script setup>

  // Lib imports
  import { ref, watch, onMounted } from 'vue';

  // antd imports
  import { SearchOutlined } from '@antdv-next/icons';

  // Components imports
  import myrange from '@/components/inputs/range.vue'

  // Style imports
  import './search.css';

  const { column, visible } = defineProps({
    clearFilters: {
      default: () => { },
      type: Function,
    },
    column: {
      default: () => ({}),
      type: Object,
    },
    confirm: {
      default: () => ({}),
      type: Function,
    },
    selectedKeys: {
      default: () => ({}),
      type: Object,
    },
    setSelectedKeys: {
      default: () => {},
      type: Function,
    },
    visible: {
      type: Boolean,
    },
  });

  const searchInput = ref();
  const handleReset = (clearFilters, confirm) => {
    clearFilters({ confirm: false });
    confirm({ closeDropdown: true });
  }

  // Watch dropdown visibility
  watch(
    () => visible,
    (value) => {
      if (!column.type && value) {
        // wait for DOM to render
        setTimeout(() => searchInput.value.focus(), 100);
      }
    }
  );

  onMounted(() => {
    !column.type && setTimeout(() => searchInput.value.focus(), 100);
  });


</script>
<template>
  <div class="table-search">
    <a-row
      v-if="column.type === 'datetime'"
      class="input-date-wrapper"
    >
      <a-range-picker
        :value="selectedKeys[0]"
        :placeholder="[$t('commons.from'), $t('commons.to')]"
        @change="(value) => setSelectedKeys(value ? [value] : [])"
      />
    </a-row>
    <a-row
      v-else-if="column.type === 'number'"
      class="input-number-wrapper"
    >
      <myrange
        :value="selectedKeys"
        :placeholder="[$t('commons.from'), $t('commons.to')]"
        @change="(value) => setSelectedKeys(value ? value : [])"
      />
    </a-row>
    <a-row
      v-else
      class="input-text-wrapper"
    >
      <a-input
        ref="searchInput"
        size="large"
        :value="selectedKeys[0]"
        @change="(event) => setSelectedKeys(event.target.value ? [event.target.value] : [])"
        @pressEnter="confirm()"
      />
    </a-row>

    <a-divider />

    <a-row class="btn-wrapper">
      <a-button
        @click="handleReset(clearFilters, confirm)"
      >
        {{ $t('commons.reset') }}
      </a-button>

      <a-button
        class="default"
        @click="confirm()"
      >
        <template #icon>
          <search-outlined />
        </template>
        {{ $t('commons.search') }}
      </a-button>
    </a-row>
  </div>
</template>
