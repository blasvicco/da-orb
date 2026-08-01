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
    chat.sendMessage(message);
    expect(sendSpy).not.toHaveBeenCalled();
  });

  it('sends a message with the default expertise level', () => {
    chat.sendMessage('hello');
    expect(sendSpy).toHaveBeenCalledWith({
      active_node_override: null,
      expertise_level: 2,
      message: 'hello',
      type: 'message.send',
    });
  });

  it('sends a message with a custom expertise level', () => {
    chat.sendMessage('hello', 3);
    expect(sendSpy).toHaveBeenCalledWith({
      active_node_override: null,
      expertise_level: 3,
      message: 'hello',
      type: 'message.send',
    });
  });

  it('sends a message with a one-shot active_node_override when provided', () => {
    chat.sendMessage('hello', 2, 'n2#0');
    expect(sendSpy).toHaveBeenCalledWith({
      active_node_override: 'n2#0',
      expertise_level: 2,
      message: 'hello',
      type: 'message.send',
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
