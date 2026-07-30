<script setup>
  import { HistoryOutlined, ShoppingCartOutlined, UnorderedListOutlined } from '@antdv-next/icons';

  import '@/components/chat/welcome.css';

  defineProps({
    userName: {
      default: '',
      type: String,
    },
  });

  defineEmits(['suggestion']);
</script>

<template>
  <div class="orb-chat-welcome">
    <div class="orb-hal-eye">
      <div class="orb-hal-iris">
        <div class="orb-hal-pupil" />
      </div>
    </div>
    <h2 class="orb-welcome-title">
      {{ $t('chat.welcome.greeting', { name: userName }) }}
    </h2>
    <p class="orb-welcome-sub">
      {{ $t('chat.welcome.sub') }}
    </p>

    <div class="orb-suggestions-grid">
      <div
        class="orb-suggestion-card"
        @click="$emit('suggestion', 'chat.suggestions.createPR.prompt')"
      >
        <span class="orb-suggestion-icon"><ShoppingCartOutlined /></span>
        <span class="orb-suggestion-title">
          {{ $t('chat.suggestions.createPR.title') }}
        </span>
        <span class="orb-suggestion-prompt">
          "{{ $t('chat.suggestions.createPR.prompt') }}"
        </span>
      </div>

      <div
        class="orb-suggestion-card"
        @click="$emit('suggestion', 'chat.suggestions.openPRs.prompt')"
      >
        <span class="orb-suggestion-icon"><UnorderedListOutlined /></span>
        <span class="orb-suggestion-title">
          {{ $t('chat.suggestions.openPRs.title') }}
        </span>
        <span class="orb-suggestion-prompt">
          "{{ $t('chat.suggestions.openPRs.prompt') }}"
        </span>
      </div>

      <div
        class="orb-suggestion-card"
        @click="$emit('suggestion', 'chat.suggestions.myRecentPR.prompt')"
      >
        <span class="orb-suggestion-icon"><HistoryOutlined /></span>
        <span class="orb-suggestion-title">
          {{ $t('chat.suggestions.myRecentPR.title') }}
        </span>
        <span class="orb-suggestion-prompt">
          "{{ $t('chat.suggestions.myRecentPR.prompt') }}"
        </span>
      </div>
    </div>
  </div>
</template>
