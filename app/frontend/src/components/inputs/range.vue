<script setup>
  // Style imports
  import './range.css';

  const { placeholder, value } = defineProps({
    placeholder: {
      default: () => ['', ''],
      type: Array,
    },
    value: {
      default: () => [],
      type: Array,
    },
  });

  const emit = defineEmits(['change']);

  const update = (index, raw) => {
    const next = [value[0], value[1]];
    next[index] = raw === '' ? undefined : raw;
    emit('change', next[0] === undefined && next[1] === undefined ? undefined : next);
  };
</script>

<template>
  <div class="input-range">
    <a-input-number
      size="large"
      :placeholder="placeholder[0]"
      :value="value[0]"
      @change="(raw) => update(0, raw)"
    />
    <span class="input-range-separator">–</span>
    <a-input-number
      size="large"
      :placeholder="placeholder[1]"
      :value="value[1]"
      @change="(raw) => update(1, raw)"
    />
  </div>
</template>
