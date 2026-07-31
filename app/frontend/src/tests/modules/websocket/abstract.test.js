// Libs imports
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// App imports
import { useAuth } from '@/modules/auth';
import Abstract from '@/modules/websocket/abstract';

// Fixtures
class TestSocket extends Abstract {
  constructor() {
    super('/ws/test/');
  }
}

describe('websocket.Abstract.constructor', () => {
  it('throws when instantiated directly', () => {
    expect(() => new Abstract('/ws/test/')).toThrow(TypeError);
  });

  it('a subclass initialises its default state', () => {
    const socket = new TestSocket();
    expect(socket.endpoint).toBe('/ws/test/');
    expect(socket.handlers).toEqual({});
    expect(socket.reconnectDelay).toBe(3000);
    expect(socket.sessionId).toBeNull();
    expect(socket.shouldReconnect).toBe(true);
    expect(socket.socket).toBeNull();
  });
});

describe('websocket.Abstract.connect', () => {
  it('creates a new WebSocket and wires up its handlers', () => {
    const socket = new TestSocket();
    socket.connect();
    expect(socket.socket).toBeInstanceOf(WebSocket);
    expect(socket.socket.onclose).toBeInstanceOf(Function);
    expect(socket.socket.onerror).toBeInstanceOf(Function);
    expect(socket.socket.onmessage).toBeInstanceOf(Function);
    expect(socket.socket.onopen).toBeInstanceOf(Function);
  });

  it('is a no-op when the socket is already open', () => {
    const socket = new TestSocket();
    socket.connect();
    socket.socket.readyState = WebSocket.OPEN;
    const openSocket = socket.socket;
    socket.connect();
    expect(socket.socket).toBe(openSocket);
  });

  it('onopen sends the auth.init payload instead of emitting open immediately', () => {
    const socket = new TestSocket();
    socket.connect();
    const sendSpy = vi.spyOn(socket, 'send');
    socket.socket.readyState = WebSocket.OPEN;
    socket.socket.onopen();
    expect(sendSpy).toHaveBeenCalledWith(expect.objectContaining({ type: 'auth.init' }));
  });
});

describe('websocket.Abstract.disconnect', () => {
  it('stops reconnecting and closes the socket', () => {
    const socket = new TestSocket();
    socket.connect();
    const closeSpy = vi.spyOn(socket.socket, 'close');
    socket.disconnect();
    expect(socket.shouldReconnect).toBe(false);
    expect(closeSpy).toHaveBeenCalled();
  });

  it('tolerates being called before connect()', () => {
    const socket = new TestSocket();
    expect(() => socket.disconnect()).not.toThrow();
  });
});

describe('websocket.Abstract.send', () => {
  it('sends JSON when the socket is open', () => {
    const socket = new TestSocket();
    socket.connect();
    socket.socket.readyState = WebSocket.OPEN;
    const sendSpy = vi.spyOn(socket.socket, 'send');
    socket.send({ type: 'message.send' });
    expect(sendSpy).toHaveBeenCalledWith(JSON.stringify({ type: 'message.send' }));
  });

  it('does nothing when the socket is not open', () => {
    const socket = new TestSocket();
    socket.connect();
    const sendSpy = vi.spyOn(socket.socket, 'send');
    socket.send({ type: 'message.send' });
    expect(sendSpy).not.toHaveBeenCalled();
  });
});

describe('websocket.Abstract.on / _emit', () => {
  it('calls every registered handler for the emitted event', () => {
    const socket = new TestSocket();
    const first = vi.fn();
    const second = vi.fn();
    socket.on('custom', first);
    socket.on('custom', second);
    socket._emit('custom', { value: 1 });
    expect(first).toHaveBeenCalledWith({ value: 1 });
    expect(second).toHaveBeenCalledWith({ value: 1 });
  });

  it('does nothing when no handler is registered for the event', () => {
    const socket = new TestSocket();
    expect(() => socket._emit('unregistered', {})).not.toThrow();
  });
});

describe('websocket.Abstract._buildUrl', () => {
  it('builds a ws(s) URL carrying the token and username from the active session', () => {
    const auth = useAuth();
    auth.callback({ access_token: 'tok', user: { username: 'bob' } });
    const socket = new TestSocket();
    const url = socket._buildUrl();
    expect(url).toContain('/ws/test/?');
    expect(url).toContain('token=tok');
    expect(url).toContain('username=bob');
  });

  it('builds a blank token/username when no session exists', () => {
    const socket = new TestSocket();
    const url = socket._buildUrl();
    expect(url).toContain('token=&username=');
  });

  it('uses wss when the page itself is served over https', () => {
    window.happyDOM.setURL('https://orb.example.com/chat');
    const socket = new TestSocket();
    const url = socket._buildUrl();
    expect(url).toMatch(/^wss:\/\//);
  });
});

describe('websocket.Abstract._sendAuthInit', () => {
  it('sends password/database from the session, and session_id when resuming', () => {
    const auth = useAuth();
    auth.callback({ database: 'TESTDB', user: { password: 'secret', username: 'bob' } });
    const socket = new TestSocket();
    socket.sessionId = 42;
    socket.connect();
    socket.socket.readyState = WebSocket.OPEN;
    const sendSpy = vi.spyOn(socket.socket, 'send');
    socket._sendAuthInit();
    expect(JSON.parse(sendSpy.mock.calls[0][0])).toEqual({
      database: 'TESTDB',
      password: 'secret',
      session_id: 42,
      type: 'auth.init',
    });
  });

  it('omits session_id when starting a brand-new chat', () => {
    const socket = new TestSocket();
    socket.connect();
    socket.socket.readyState = WebSocket.OPEN;
    const sendSpy = vi.spyOn(socket.socket, 'send');
    socket._sendAuthInit();
    const sent = JSON.parse(sendSpy.mock.calls[0][0]);
    expect(sent).not.toHaveProperty('session_id');
  });
});

describe('websocket.Abstract.onerror', () => {
  it('emits an error event through the wired-up onerror handler', () => {
    const socket = new TestSocket();
    socket.connect();
    const errorHandler = vi.fn();
    socket.on('error', errorHandler);

    socket.socket.onerror({ message: 'boom' });

    expect(errorHandler).toHaveBeenCalledWith({ message: 'boom' });
  });
});

describe('websocket.Abstract._onClose (via the wired-up onclose handler)', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('emits close and schedules a reconnect with exponential backoff', () => {
    const socket = new TestSocket();
    socket.connect();
    const closeHandler = vi.fn();
    socket.on('close', closeHandler);
    const connectSpy = vi.spyOn(socket, 'connect').mockImplementation(() => {});

    socket.socket.onclose({ code: 1006 });

    expect(closeHandler).toHaveBeenCalledWith({ code: 1006 });
    expect(socket.reconnectDelay).toBe(4500); // 3000 * 1.5

    vi.advanceTimersByTime(4500);
    expect(connectSpy).toHaveBeenCalledTimes(1);
  });

  it('caps the backoff delay at 30 seconds', () => {
    const socket = new TestSocket();
    socket.connect();
    vi.spyOn(socket, 'connect').mockImplementation(() => {});
    socket.reconnectDelay = 25000;

    socket.socket.onclose({ code: 1006 });

    expect(socket.reconnectDelay).toBe(30000);
  });

  it('does not schedule a reconnect once disconnect() was called', () => {
    const socket = new TestSocket();
    socket.connect();
    const connectSpy = vi.spyOn(socket, 'connect').mockImplementation(() => {});
    socket.shouldReconnect = false;

    socket.socket.onclose({ code: 1000 });
    vi.advanceTimersByTime(30000);

    expect(connectSpy).not.toHaveBeenCalled();
  });
});

describe('websocket.Abstract._onMessage (via the wired-up onmessage handler)', () => {
  it('emits open and auth (not the raw type handlers) for an auth.ok message', () => {
    const socket = new TestSocket();
    socket.connect();
    const openHandler = vi.fn();
    const authHandler = vi.fn();
    socket.on('open', openHandler);
    socket.on('auth', authHandler);

    socket.socket.onmessage({ data: JSON.stringify({ session_id: 7, type: 'auth.ok' }) });

    expect(openHandler).toHaveBeenCalled();
    expect(authHandler).toHaveBeenCalledWith({ session_id: 7, type: 'auth.ok' });
  });

  it('dispatches to type-specific handlers and always emits message', () => {
    const socket = new TestSocket();
    socket.connect();
    const agentHandler = vi.fn();
    const messageHandler = vi.fn();
    socket.on('agent', agentHandler);
    socket.on('message', messageHandler);

    const data = { text: 'hi', type: 'agent' };
    socket.socket.onmessage({ data: JSON.stringify(data) });

    expect(agentHandler).toHaveBeenCalledWith(data);
    expect(messageHandler).toHaveBeenCalledWith(data);
  });

  it('logs instead of throwing when the payload is not valid JSON', () => {
    const socket = new TestSocket();
    socket.connect();
    expect(() => socket.socket.onmessage({ data: 'not-json' })).not.toThrow();
    expect(console.error).toHaveBeenCalled();
  });

  it('still emits message for a type with no registered handler', () => {
    const socket = new TestSocket();
    socket.connect();
    const messageHandler = vi.fn();
    socket.on('message', messageHandler);

    const data = { text: 'ping', type: 'unregistered' };
    expect(() => socket.socket.onmessage({ data: JSON.stringify(data) })).not.toThrow();

    expect(messageHandler).toHaveBeenCalledWith(data);
  });
});
