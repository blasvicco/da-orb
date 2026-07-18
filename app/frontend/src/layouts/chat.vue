<script setup>
  import '@/layouts/chat.css';

  defineProps({
    theme: {
      default: 'light',
      type: String,
    },
  });
</script>

<template>
  <div
    class="orb-chat-layout"
    :data-theme="theme"
  >
    <aside class="orb-sidebar">
      <div class="orb-sidebar-top">
        <slot name="sidebar-top" />
      </div>
      <slot name="sidebar-bottom" />
    </aside>

    <main class="orb-chat-pane">
      <slot />
    </main>
  </div>
</template>
