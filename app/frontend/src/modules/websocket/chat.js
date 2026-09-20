import Abstract from './abstract';

export default class Chat extends Abstract {
  constructor() {
    super('/ws/chat/');
  }

  /**
   * Ask the backend to create the DB session now, ahead of any real message —
   * e.g. right when a file is attached to a brand-new chat, so its upload has
   * a real session_id to target. Response arrives as a 'session.created' event.
   */
  ensureSession() {
    this.send({ type: 'session.ensure' });
  }

  /**
   * Ask the backend to switch the active Intention Graph node — triggered by the
   * user clicking a node in the sidebar and confirming the context switch. Resolved
   * directly against Redis server-side, no n8n round-trip involved. `text` is the
   * already-translated announcement (e.g. "Context switched — now in **X**.") for
   * the backend to broadcast back as a 'system' message and persist, so it appears
   * in chat history on reload the same way a typed message would — omit it to move
   * the active node with no chat bubble at all.
   */
  switchActiveNode(nodeId, text) {
    this.send({ active_node_id: nodeId, text, type: 'active_node.switch' });
  }

  /** Register a handler for agent replies */
  onAgentMessage(handler) {
    this.on('agent', handler);
  }

  /** Register a handler for error/alert notices from the backend */
  onAlertMessage(handler) {
    this.on('alert', handler);
  }

  /** Register a handler for the auth.ok event (receives {session_id, ...}) */
  onAuth(handler) {
    this.on('auth', handler);
  }

  /** Register a handler for SAP-data card messages */
  onSapData(handler) {
    this.on('sap-data', handler);
  }

  /** Register a handler for ephemeral workflow status updates */
  onStatusMessage(handler) {
    this.on('status', handler);
  }

  /** Register a handler for transient system notices (e.g. "please wait") */
  onSystemMessage(handler) {
    this.on('system', handler);
  }

  /** Register a handler for echoed user messages */
  onUserMessage(handler) {
    this.on('user', handler);
  }

  /**
   * Send a user chat message, optionally carrying bucket file ids attached as context.
   * `language` and `expertiseLevel` are always required, never defaulted here, so the
   * backend/n8n always know exactly what the user has selected right now.
   */
  sendMessage(message, language, expertiseLevel, contextFileIds = []) {
    if (!message || !message.trim()) return;
    this.send({
      bucket_file_ids: contextFileIds,
      expertise_level: expertiseLevel,
      language,
      message,
      type: 'message.send',
    });
  }
}
