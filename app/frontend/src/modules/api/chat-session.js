import Abstract from './abstract';

// list() is inherited from Abstract: it already speaks the {filters, sorter, limit, offset}
// <-> {count, results} contract VSChatSession serves (filter by project with project_id).
class ChatSession extends Abstract {
  constructor() {
    super();
    this.resource = 'chat_session';
    this._updateEndpoint();
  }

  // Moves every given chat to another project, all or nothing.
  async move(sessionIds, projectId) {
    const res = await fetch(
      `${this.constants.ENDPOINT}/move/`,
      {
        body: JSON.stringify({ project_id: projectId, session_ids: sessionIds }),
        credentials: 'include',
        headers: { ...this.header(), 'Content-Type': 'application/json' },
        method: 'POST',
      },
    );
    return this._handleError(res);
  }
}

export default new ChatSession();
