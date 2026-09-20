// Libs imports
import { beforeEach, describe, expect, it, vi } from 'vitest';

// App imports
import Chat from '@/modules/websocket/chat';

describe('websocket.Chat.constructor', () => {
  it('connects to the chat endpoint', () => {
    const chat = new Chat();
    expect(chat.endpoint).toBe('/ws/chat/');
  });
});

describe('websocket.Chat.sendMessage', () => {
  let chat;
  let sendSpy;

  beforeEach(() => {
    chat = new Chat();
    sendSpy = vi.spyOn(chat, 'send').mockImplementation(() => {});
  });

  it.each([
    ['an empty message is not sent', ''],
    ['a whitespace-only message is not sent', '   '],
  ])('%s', (_label, message) => {
    chat.sendMessage(message, 'es', 2);
    expect(sendSpy).not.toHaveBeenCalled();
  });

  it('sends whatever expertise level the caller currently has selected, with no default of its own', () => {
    chat.sendMessage('hello', 'es', 3);
    expect(sendSpy).toHaveBeenCalledWith({
      bucket_file_ids: [],
      expertise_level: 3,
      language: 'es',
      message: 'hello',
      type: 'message.send',
    });
  });

  it('sends a message with bucket_file_ids context references when provided', () => {
    chat.sendMessage('hello', 'es', 2, [7, 8]);
    expect(sendSpy).toHaveBeenCalledWith({
      bucket_file_ids: [7, 8],
      expertise_level: 2,
      language: 'es',
      message: 'hello',
      type: 'message.send',
    });
  });

  it('sends whatever language the caller currently has selected, with no default of its own', () => {
    chat.sendMessage('hello', 'en', 2);
    expect(sendSpy).toHaveBeenCalledWith({
      bucket_file_ids: [],
      expertise_level: 2,
      language: 'en',
      message: 'hello',
      type: 'message.send',
    });
  });
});

describe('websocket.Chat.ensureSession', () => {
  it('sends a session.ensure request', () => {
    const chat = new Chat();
    const sendSpy = vi.spyOn(chat, 'send').mockImplementation(() => {});
    chat.ensureSession();
    expect(sendSpy).toHaveBeenCalledWith({ type: 'session.ensure' });
  });
});

describe('websocket.Chat.switchActiveNode', () => {
  it('sends an active_node.switch request carrying the target node id and announcement text', () => {
    const chat = new Chat();
    const sendSpy = vi.spyOn(chat, 'send').mockImplementation(() => {});
    chat.switchActiveNode('n2#0', 'Context switched — now in Vendor List.');
    expect(sendSpy).toHaveBeenCalledWith({
      active_node_id: 'n2#0',
      text: 'Context switched — now in Vendor List.',
      type: 'active_node.switch',
    });
  });
});

describe('websocket.Chat event registration', () => {
  it.each([
    ['onAuth registers an auth handler', 'onAuth', 'auth'],
    ['onUserMessage registers a user handler', 'onUserMessage', 'user'],
    ['onAgentMessage registers an agent handler', 'onAgentMessage', 'agent'],
    ['onSapData registers a sap-data handler', 'onSapData', 'sap-data'],
    ['onSystemMessage registers a system handler', 'onSystemMessage', 'system'],
    ['onAlertMessage registers an alert handler', 'onAlertMessage', 'alert'],
    ['onStatusMessage registers a status handler', 'onStatusMessage', 'status'],
  ])('%s', (_label, method, eventType) => {
    const chat = new Chat();
    const handler = vi.fn();
    chat[method](handler);
    chat._emit(eventType, { payload: true });
    expect(handler).toHaveBeenCalledWith({ payload: true });
  });
});
