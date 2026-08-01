import Abstract from './abstract';

export default class Chat extends Abstract {
  constructor() {
    super('/ws/chat/');
  }

  /** Send a user chat message, optionally carrying a one-shot Intention Graph navigation override */
  sendMessage(message, expertiseLevel = 2, activeNodeOverride = null) {
    if (!message || !message.trim()) return;
    this.send({
      active_node_override: activeNodeOverride,
      expertise_level: expertiseLevel,
      message,
      type: 'message.send',
    });
  }

  /** Register a handler for the auth.ok event (receives {session_id, ...}) */
  onAuth(handler) {
    this.on('auth', handler);
  }

  /** Register a handler for echoed user messages */
  onUserMessage(handler) {
    this.on('user', handler);
  }

  /** Register a handler for agent replies */
  onAgentMessage(handler) {
    this.on('agent', handler);
  }

  /** Register a handler for SAP-data card messages */
  onSapData(handler) {
    this.on('sap-data', handler);
  }

  /** Register a handler for transient system notices (e.g. "please wait") */
  onSystemMessage(handler) {
    this.on('system', handler);
  }

  /** Register a handler for error/alert notices from the backend */
  onAlertMessage(handler) {
    this.on('alert', handler);
  }

  /** Register a handler for ephemeral workflow status updates */
  onStatusMessage(handler) {
    this.on('status', handler);
  }
}
