import Abstract from './abstract';

class Chat extends Abstract {
  constructor() {
    super();
    this.resource = 'chat';
    this._updateEndpoint();
  }

  async sessions(projectId) {
    const res = await fetch(
      `${this.constants.ENDPOINT}/sessions/?project_id=${projectId}`,
      { credentials: 'include', headers: this.header() },
    );
    return this._handleError(res);
  }

  // The few most recent sessions across every project, for the sidebar's Recent Chats.
  async recent() {
    const res = await fetch(
      `${this.constants.ENDPOINT}/recent/`,
      { credentials: 'include', headers: this.header() },
    );
    return this._handleError(res);
  }

  async messages(sessionId) {
    const res = await fetch(
      `${this.constants.ENDPOINT}/messages/?session_id=${sessionId}`,
      { credentials: 'include', headers: this.header() },
    );
    return this._handleError(res);
  }

  async deleteSession(sessionId) {
    const res = await fetch(
      `${this.constants.ENDPOINT}/delete_session/?session_id=${sessionId}`,
      { method: 'DELETE', credentials: 'include', headers: this.header() },
    );
    return this._handleError(res);
  }
}

export default new Chat();
