import { enableAutoUnmount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { afterEach, beforeEach, vi } from 'vitest';

// antdv-next popups/modals teleport content onto document.body; without unmounting
// each wrapper, a popup left open at the end of a test leaks into the next one.
enableAutoUnmount(afterEach);

globalThis.fetch = vi.fn();

class MockWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;

  constructor(url) {
    this.url = url;
    this.readyState = MockWebSocket.CONNECTING;
    this.onclose = null;
    this.onerror = null;
    this.onmessage = null;
    this.onopen = null;
  }

  close() {
    this.readyState = MockWebSocket.CLOSED;
  }

  send() {}
}

globalThis.WebSocket = MockWebSocket;

vi.spyOn(console, 'error').mockImplementation(() => {});
vi.spyOn(console, 'warn').mockImplementation(() => {});

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
  globalThis.fetch.mockReset();
  setActivePinia(createPinia());
});
