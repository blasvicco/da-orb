// Libs imports
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// App imports
import { body, mount } from '@/tests/helpers/mount';
import Export from '@/components/chat/export.vue';

const USER_MESSAGE = { text: 'What is the stock level?', time: '10:00', type: 'user' };
const AGENT_MESSAGE = { text: '**In stock**: 42 units', time: '10:01', type: 'agent' };
const SAP_MESSAGE = {
  data: { 'landing.chat.step3.inStock': 'landing.chat.step3.inStockVal' },
  time: '10:02',
  titleKey: 'landing.chat.step3.title',
  type: 'sap-data',
};
const SAP_MESSAGE_NO_DATA = { time: '10:03', titleKey: 'x.title', type: 'sap-data' };
const MESSAGE_NO_TEXT = { time: '10:04', type: 'agent' };
const UNKNOWN_TYPE_NO_TEXT = { time: '10:05', type: 'unknown' };

// a-popover uses trigger="click" and only mounts (teleported) content once opened.
const openExportPanel = async (wrapper) => {
  await wrapper.find('.orb-prompt-tool-btn').trigger('click');
};

describe('Export visibility', () => {
  it('renders nothing when there are no messages', () => {
    const wrapper = mount(Export, { props: { messages: [] } });
    expect(wrapper.find('.orb-prompt-tool-btn').exists()).toBe(false);
  });

  it('renders the export trigger once messages exist', () => {
    const wrapper = mount(Export, { props: { messages: [USER_MESSAGE] } });
    expect(wrapper.find('.orb-prompt-tool-btn').exists()).toBe(true);
  });
});

describe('Export downloads', () => {
  let createObjectURL;
  let revokeObjectURL;
  let clickSpy;
  let capturedBlob;
  let capturedFilename;

  beforeEach(() => {
    capturedBlob = null;
    capturedFilename = null;
    createObjectURL = vi.fn((blob) => {
      capturedBlob = blob;
      return 'blob:mock-url';
    });
    revokeObjectURL = vi.fn();
    URL.createObjectURL = createObjectURL;
    URL.revokeObjectURL = revokeObjectURL;
    clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function capture() {
      capturedFilename = this.download;
    });
  });

  afterEach(() => {
    clickSpy.mockRestore();
  });

  it('exports as text with a sender/time/body line per message', async () => {
    const wrapper = mount(Export, {
      props: { messages: [USER_MESSAGE, AGENT_MESSAGE], sessionTitle: 'Stock Check', userName: 'Bob' },
    });
    await openExportPanel(wrapper);
    await body().find('.orb-export-option').trigger('click');

    expect(createObjectURL).toHaveBeenCalled();
    expect(clickSpy).toHaveBeenCalled();
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:mock-url');
    const text = await capturedBlob.text();
    expect(text).toContain('Stock Check');
    expect(text).toContain('Bob');
    expect(text).toContain('What is the stock level?');
  });

  it('exports as markdown', async () => {
    const wrapper = mount(Export, { props: { messages: [USER_MESSAGE] } });
    await openExportPanel(wrapper);
    const buttons = body().findAll('.orb-export-option');
    await buttons[1].trigger('click');

    const text = await capturedBlob.text();
    expect(text).toContain('#');
    expect(capturedBlob.type).toContain('text/markdown');
  });

  it('exports as JSON with the full message list, title, and session id', async () => {
    const wrapper = mount(Export, {
      props: { messages: [USER_MESSAGE], sessionId: 208, sessionTitle: 'Stock Check' },
    });
    await openExportPanel(wrapper);
    const buttons = body().findAll('.orb-export-option');
    await buttons[3].trigger('click');

    const payload = JSON.parse(await capturedBlob.text());
    expect(payload.title).toBe('Stock Check');
    expect(payload.messages).toEqual([USER_MESSAGE]);
    expect(payload.sessionId).toBe(208);
  });

  it('exports as JSON with a null sessionId when unset', async () => {
    const wrapper = mount(Export, { props: { messages: [USER_MESSAGE] } });
    await openExportPanel(wrapper);
    const buttons = body().findAll('.orb-export-option');
    await buttons[3].trigger('click');

    const payload = JSON.parse(await capturedBlob.text());
    expect(payload.sessionId).toBeNull();
  });

  it('includes the session id line in text and markdown exports when set', async () => {
    const wrapper = mount(Export, { props: { messages: [USER_MESSAGE], sessionId: 208 } });
    await openExportPanel(wrapper);
    await body().find('.orb-export-option').trigger('click');

    const text = await capturedBlob.text();
    expect(text).toContain('208');
  });

  it('omits the session id line entirely when unset', async () => {
    const wrapper = mount(Export, { props: { messages: [USER_MESSAGE] } });
    await openExportPanel(wrapper);
    await body().find('.orb-export-option').trigger('click');

    const text = await capturedBlob.text();
    expect(text).not.toContain('Session ID');
  });

  it('falls back to "chat" and Orb as sender/title defaults when unset', async () => {
    const wrapper = mount(Export, { props: { messages: [AGENT_MESSAGE] } });
    await openExportPanel(wrapper);
    const buttons = body().findAll('.orb-export-option');
    await buttons[0].trigger('click');

    const text = await capturedBlob.text();
    expect(text).toContain('Orb');
  });

  it('renders a sap-data message body as labelled lines in text export', async () => {
    const wrapper = mount(Export, { props: { messages: [SAP_MESSAGE] } });
    await openExportPanel(wrapper);
    await body().find('.orb-export-option').trigger('click');

    expect(createObjectURL).toHaveBeenCalled();
  });

  it('treats a sap-data message with no data as an empty key/value list in text export', async () => {
    const wrapper = mount(Export, { props: { messages: [SAP_MESSAGE_NO_DATA] } });
    await openExportPanel(wrapper);
    await body().find('.orb-export-option').trigger('click');

    expect(createObjectURL).toHaveBeenCalled();
  });

  it('treats a missing message body as empty text in text export', async () => {
    const wrapper = mount(Export, { props: { messages: [MESSAGE_NO_TEXT] } });
    await openExportPanel(wrapper);
    await body().find('.orb-export-option').trigger('click');

    const text = await capturedBlob.text();
    expect(text).toContain(MESSAGE_NO_TEXT.time);
  });

  it('exports as JSON with a null title when no sessionTitle is set', async () => {
    const wrapper = mount(Export, { props: { messages: [USER_MESSAGE] } });
    await openExportPanel(wrapper);
    const buttons = body().findAll('.orb-export-option');
    await buttons[3].trigger('click');

    const payload = JSON.parse(await capturedBlob.text());
    expect(payload.title).toBeNull();
  });

  it('falls back to a plain "chat" filename when the session title strips to nothing', async () => {
    const wrapper = mount(Export, { props: { messages: [USER_MESSAGE], sessionTitle: '!!!' } });
    await openExportPanel(wrapper);
    await body().find('.orb-export-option').trigger('click');

    expect(capturedFilename).toMatch(/^chat-\d{4}-\d{2}-\d{2}\.txt$/);
  });
});

describe('Export PDF', () => {
  it('includes the session id in the PDF header when set', async () => {
    const wrapper = mount(Export, { props: { messages: [USER_MESSAGE], sessionId: 208 } });
    await openExportPanel(wrapper);
    await body().findAll('.orb-export-option')[2].trigger('click');

    const iframe = document.querySelector('iframe');
    expect(iframe.srcdoc).toContain('208');
    document.body.removeChild(iframe);
  });

  it('builds a printable iframe document containing every message', async () => {
    const wrapper = mount(Export, {
      props: { messages: [USER_MESSAGE, AGENT_MESSAGE, SAP_MESSAGE], sessionTitle: 'Stock Check' },
    });
    await openExportPanel(wrapper);
    const buttons = body().findAll('.orb-export-option');

    await buttons[2].trigger('click');

    const iframe = document.querySelector('iframe');
    expect(iframe).not.toBeNull();
    expect(iframe.srcdoc).toContain('Stock Check');
    expect(iframe.srcdoc).toContain('In stock');
    document.body.removeChild(iframe);
  });

  it('renders a nameless (unstyled) message type with no text as an empty body', async () => {
    const wrapper = mount(Export, { props: { messages: [UNKNOWN_TYPE_NO_TEXT] } });
    await openExportPanel(wrapper);
    await body().findAll('.orb-export-option')[2].trigger('click');

    const iframe = document.querySelector('iframe');
    expect(iframe).not.toBeNull();
    document.body.removeChild(iframe);
  });

  it('renders a sap-data message with no data as an empty table', async () => {
    const wrapper = mount(Export, { props: { messages: [SAP_MESSAGE_NO_DATA] } });
    await openExportPanel(wrapper);
    await body().findAll('.orb-export-option')[2].trigger('click');

    const iframe = document.querySelector('iframe');
    expect(iframe).not.toBeNull();
    document.body.removeChild(iframe);
  });

  it('focuses and prints the iframe once it finishes loading, then cleans it up via onafterprint', async () => {
    const wrapper = mount(Export, { props: { messages: [USER_MESSAGE] } });
    await openExportPanel(wrapper);
    await body().findAll('.orb-export-option')[2].trigger('click');
    const iframe = document.querySelector('iframe');
    const focusSpy = vi.fn();
    const printSpy = vi.fn();
    const fakeWindow = { focus: focusSpy, print: printSpy };
    Object.defineProperty(iframe, 'contentWindow', { configurable: true, value: fakeWindow });

    iframe.onload();

    expect(focusSpy).toHaveBeenCalled();
    expect(printSpy).toHaveBeenCalled();
    expect(document.querySelector('iframe')).not.toBeNull();

    fakeWindow.onafterprint();
    expect(document.querySelector('iframe')).toBeNull();

    // A later cleanup call (e.g. the 60s fallback timer) once already detached
    // must be a safe no-op, not a crash.
    expect(() => fakeWindow.onafterprint()).not.toThrow();
  });

  it('does nothing if the iframe was detached before it finished loading', async () => {
    const wrapper = mount(Export, { props: { messages: [USER_MESSAGE] } });
    await openExportPanel(wrapper);
    await body().findAll('.orb-export-option')[2].trigger('click');
    const iframe = document.querySelector('iframe');
    document.body.removeChild(iframe);

    expect(() => iframe.onload()).not.toThrow();
  });
});
