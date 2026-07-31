<script setup>
  import { nextTick, ref, watch } from 'vue';

  import '@/components/chat/input.css';

  const props = defineProps({
    disabled: {
      default: false,
      type: Boolean,
    },
    modelValue: {
      default: '',
      type: String,
    },
  });

  const emit = defineEmits(['send', 'update:modelValue']);

  const promptTextarea = ref(null);

  const resizeTextarea = () => {
    const el = promptTextarea.value;
    // v8 ignore next -- textarea is unconditionally rendered; unreachable pre-mount/post-unmount.
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${el.scrollHeight}px`;
  };

  watch(() => props.modelValue, async () => {
    await nextTick();
    resizeTextarea();
  });

  const handleKeydown = (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      emit('send');
    }
  };

  const onInput = (event) => {
    emit('update:modelValue', event.target.value);
    resizeTextarea();
  };
</script>

<template>
  <div class="orb-prompt-wrapper">
    <div class="orb-prompt-bar">
      <textarea
        ref="promptTextarea"
        :value="modelValue"
        rows="1"
        class="orb-prompt-input"
        :placeholder="$t('chat.input.placeholder')"
        @input="onInput"
        @keydown="handleKeydown"
      />
      <button
        class="orb-prompt-send-btn"
        :disabled="!modelValue.trim() || disabled"
        :title="$t('chat.input.sendInquiry')"
        @click="emit('send')"
      >
        ➔
      </button>
    </div>
    <div class="orb-prompt-footnote">
      {{ $t('chat.input.info') }}
    </div>
  </div>
</template>
