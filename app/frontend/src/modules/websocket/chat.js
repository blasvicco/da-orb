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
   * Send a user chat message, optionally carrying a one-shot Intention Graph
   * navigation override and/or bucket file ids attached as context.
   */
  sendMessage(message, expertiseLevel = 2, activeNodeOverride = null, contextFileIds = []) {
    if (!message || !message.trim()) return;
    this.send({
      active_node_override: activeNodeOverride,
      bucket_file_ids: contextFileIds,
      expertise_level: expertiseLevel,
      message,
      type: 'message.send',
    });
  }
}
