<script setup>
  import { marked } from 'marked';
  import { useI18n } from 'vue-i18n';

  // Antd imports
  import { DownloadOutlined } from '@antdv-next/icons';

  import '@/components/chat/export.css';

  const props = defineProps({
    messages: {
      default: () => [],
      type: Array,
    },
    sessionTitle: {
      default: null,
      type: String,
    },
    userName: {
      default: '',
      type: String,
    },
  });

  const { t } = useI18n();

  const renderMd = (text) => marked.parse(text || '', { breaks: true });

  const exportFilenameBase = () => {
    const title = (props.sessionTitle || 'chat').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
    return `${title || 'chat'}-${new Date().toISOString().slice(0, 10)}`;
  };

  const exportSenderLabel = (msg) => {
    if (msg.type === 'user') return props.userName || t('chat.export.you');
    return 'Orb';
  };

  const exportMessageBody = (msg) => {
    if (msg.type === 'sap-data') {
      const lines = Object.entries(msg.data || {}).map(([labelKey, valKey]) => `${t(labelKey)}: ${t(valKey)}`);
      return [`${t(msg.titleKey)}`, ...lines].join('\n');
    }
    return msg.text || '';
  };

  const downloadBlob = (filename, content, mime) => {
    const blob = new Blob([content], { type: mime });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
  };

  const exportAsText = () => {
    const header = `${props.sessionTitle || t('chat.export.untitled')}\n${t('chat.export.exportedOn')}: ${new Date().toLocaleString()}\n`;
    const body = props.messages
      .map((msg) => `[${msg.time}] ${exportSenderLabel(msg)}: ${exportMessageBody(msg)}`)
      .join('\n\n');
    downloadBlob(`${exportFilenameBase()}.txt`, `${header}\n${body}\n`, 'text/plain;charset=utf-8');
  };

  const exportAsMarkdown = () => {
    const header = `# ${props.sessionTitle || t('chat.export.untitled')}\n\n_${t('chat.export.exportedOn')}: ${new Date().toLocaleString()}_\n`;
    const body = props.messages
      .map((msg) => `**${exportSenderLabel(msg)}** — ${msg.time}\n\n${exportMessageBody(msg)}`)
      .join('\n\n---\n\n');
    downloadBlob(`${exportFilenameBase()}.md`, `${header}\n${body}\n`, 'text/markdown;charset=utf-8');
  };

  const exportAsJson = () => {
    const payload = {
      exportedOn: new Date().toISOString(),
      messages: props.messages,
      title: props.sessionTitle || null,
    };
    downloadBlob(`${exportFilenameBase()}.json`, JSON.stringify(payload, null, 2), 'application/json;charset=utf-8');
  };

  const PDF_SENDER_COLORS = {
    agent: '#107a6e',
    alert: '#be2828',
    'sap-data': '#107a6e',
    system: '#787878',
    user: '#6c5ce7',
  };

  const exportMessageBodyHtml = (msg) => {
    if (msg.type === 'sap-data') {
      const rows = Object.entries(msg.data || {})
        .map(([labelKey, valKey]) => `<tr><td class="orb-pdf-label">${t(labelKey)}</td><td class="orb-pdf-value">${t(valKey)}</td></tr>`)
        .join('');
      return `<p><strong>${t(msg.titleKey)}</strong></p><table class="orb-pdf-data">${rows}</table>`;
    }
    return renderMd(msg.text);
  };

  const exportAsPdf = () => {
    const title = props.sessionTitle || t('chat.export.untitled');
    const messagesHtml = props.messages
      .map((msg) => {
        const color = PDF_SENDER_COLORS[msg.type] || PDF_SENDER_COLORS.agent;
        const align = msg.type === 'user' ? 'right' : 'left';
        return `
          <div class="orb-pdf-msg" style="text-align:${align}">
            <div class="orb-pdf-msg-meta" style="color:${color}">${exportSenderLabel(msg)} — ${msg.time}</div>
            <div class="orb-pdf-msg-body">${exportMessageBodyHtml(msg)}</div>
          </div>`;
      })
      .join('');

    const doc = `<!DOCTYPE html>
      <html>
        <head>
          <meta charset="utf-8">
          <title>${exportFilenameBase()}</title>
          <style>
            @page { margin: 24mm 18mm; }
            body { font-family: Arial, Helvetica, sans-serif; color: #222; font-size: 12px; }
            h1 { font-size: 18px; margin: 0 0 4px; }
            .orb-pdf-exported-on { color: #888; font-size: 10px; margin: 0 0 20px; }
            .orb-pdf-msg { margin: 0 0 14px; page-break-inside: avoid; }
            .orb-pdf-msg-meta { font-weight: bold; font-size: 11px; margin-bottom: 2px; }
            .orb-pdf-msg-body { display: inline-block; max-width: 85%; text-align: left; }
            .orb-pdf-msg-body :first-child { margin-top: 0; }
            .orb-pdf-msg-body :last-child { margin-bottom: 0; }
            .orb-pdf-msg-body h1, .orb-pdf-msg-body h2 { font-size: 14px; margin: 8px 0 4px; }
            .orb-pdf-msg-body h3, .orb-pdf-msg-body h4 { font-size: 13px; margin: 8px 0 4px; }
            .orb-pdf-msg-body ul, .orb-pdf-msg-body ol { margin: 4px 0; padding-left: 20px; }
            .orb-pdf-msg-body p { margin: 4px 0; }
            .orb-pdf-msg-body code { font-family: 'Courier New', monospace; background: #f0f0f0; padding: 1px 4px; border-radius: 3px; }
            .orb-pdf-msg-body pre { background: #f0f0f0; padding: 8px; border-radius: 6px; overflow-x: auto; }
            .orb-pdf-msg-body pre code { background: none; padding: 0; }
            .orb-pdf-msg-body blockquote { border-left: 3px solid #ccc; margin: 4px 0; padding: 2px 10px; color: #555; }
            .orb-pdf-msg-body table, .orb-pdf-data { border-collapse: collapse; margin: 6px 0; width: 100%; }
            .orb-pdf-msg-body th, .orb-pdf-msg-body td, .orb-pdf-data td { border: 1px solid #ccc; padding: 4px 8px; font-size: 11px; }
            .orb-pdf-msg-body th { background: #f3f3f3; text-align: left; }
            .orb-pdf-data .orb-pdf-label { color: #666; }
            .orb-pdf-data .orb-pdf-value { font-weight: bold; }
          </style>
        </head>
        <body>
          <h1>${title}</h1>
          <p class="orb-pdf-exported-on">${t('chat.export.exportedOn')}: ${new Date().toLocaleString()}</p>
          ${messagesHtml}
        </body>
      </html>`;

    const iframe = document.createElement('iframe');
    iframe.style.border = '0';
    iframe.style.bottom = '0';
    iframe.style.height = '0';
    iframe.style.position = 'fixed';
    iframe.style.right = '0';
    iframe.style.width = '0';
    document.body.appendChild(iframe);

    const cleanup = () => iframe.parentNode && document.body.removeChild(iframe);
    iframe.onload = () => {
      // contentWindow can be null if the iframe was detached before load fired.
      const win = iframe.contentWindow;
      if (!win) return;
      win.focus();
      win.print();
      win.onafterprint = cleanup;
      // Fallback in case the browser doesn't fire `afterprint` (e.g. the user cancels)
      setTimeout(cleanup, 60000);
    };
    iframe.srcdoc = doc;
  };
</script>

<template>
  <a-popover
    v-if="messages.length > 0"
    placement="bottomRight"
    trigger="click"
  >
    <template #title>
      <span>{{ $t('chat.export.title') }}</span>
    </template>
    <template #content>
      <div class="orb-export-panel">
        <button
          class="orb-export-option"
          @click="exportAsText"
        >
          {{ $t('chat.export.text') }}
        </button>
        <button
          class="orb-export-option"
          @click="exportAsMarkdown"
        >
          {{ $t('chat.export.markdown') }}
        </button>
        <button
          class="orb-export-option"
          @click="exportAsPdf"
        >
          {{ $t('chat.export.pdf') }}
        </button>
        <button
          class="orb-export-option"
          @click="exportAsJson"
        >
          {{ $t('chat.export.json') }}
        </button>
      </div>
    </template>
    <button
      class="orb-prompt-tool-btn"
      :title="$t('chat.export.title')"
    >
      <DownloadOutlined />
    </button>
  </a-popover>
</template>
