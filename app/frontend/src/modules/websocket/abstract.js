import { useAuth } from '@/modules/auth';

export default class Abstract {

  constructor(endpoint) {
    if (new.target === Abstract) {
      throw new TypeError('Cannot instantiate Abstract directly');
    }
    this.endpoint = endpoint;
    this.handlers = {}; // keyed by message type
    this.reconnectDelay = 3000;
    this.sessionId = null; // set to resume an existing session on next connect
    this.shouldReconnect = true;
    this.socket = null;
  }

  /** Connect socket */
  connect() {
    if (this.socket?.readyState === WebSocket.OPEN) return;
    const url = this._buildUrl();
    this.socket = new WebSocket(url);
    this.socket.onclose = (event) => this._onClose(event);
    this.socket.onerror = (event) => this._emit('error', event);
    this.socket.onmessage = (event) => this._onMessage(event);
    // Don't emit 'open' yet — send credentials over the encrypted channel first.
    this.socket.onopen = () => this._sendAuthInit();
  }

  /** Disconnect socket */
  disconnect() {
    this.shouldReconnect = false;
    this.socket?.close();
  }

  /** Send JSON payload */
  send(payload) {
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(payload));
    }
  }

  /** Subscribe to events by type */
  on(type, handler) {
    if (!this.handlers[type]) this.handlers[type] = [];
    this.handlers[type].push(handler);
  }

  /** Build WS URL — only non-secret identity params go in the URL. */
  _buildUrl() {
    const auth = useAuth();
    const session = auth.getSession() || {};
    const token = session.access_token || '';
    const username = session.user?.username || '';
    const host = window.location.host.replace(':5173', ':8000');
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const params = new URLSearchParams({ token, username });
    return `${protocol}://${host}${this.endpoint}?${params.toString()}`;
  }

  /** Send sensitive credentials over the encrypted WS channel instead of the URL. */
  _sendAuthInit() {
    const auth = useAuth();
    const session = auth.getSession() || {};
    const payload = {
      type: 'auth.init',
      password: session.user?.password || '',
      database: session.database || '',
    };
    if (this.sessionId) payload.session_id = this.sessionId;
    this.send(payload);
  }

  /** Internal emit */
  _emit(event, payload) {
    if (this.handlers[event]) {
      this.handlers[event].forEach((callback) => callback(payload));
    }
  }

  /** Handle close + reconnect */
  _onClose(event) {
    this._emit('close', event);
    if (this.shouldReconnect) {
      setTimeout(() => this.connect(), this.reconnectDelay);
      this.reconnectDelay = Math.min(this.reconnectDelay * 1.5, 30000); // backoff
    }
  }

  /** Internal message handler */
  _onMessage(event) {
    try {
      const data = JSON.parse(event.data);
      const type = data.type;

      // auth.ok confirms the backend has fully initialised the session.
      if (type === 'auth.ok') {
        this._emit('open', event);
        this._emit('auth', data); // carries session_id and any other auth context
        return;
      }

      if (type && this.handlers[type]) {
        this.handlers[type].forEach((callback) => callback(data));
      }
      this._emit('message', data);
    } catch (err) {
      console.error('WS parse error:', err);
    }
  }

}
