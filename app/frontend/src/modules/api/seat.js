import Abstract from './abstract';

class Seat extends Abstract {
  constructor() {
    super();
    this.resource = 'seat';
    this._updateEndpoint();
  }

  async seats() {
    const res = await fetch(
      `${this.constants.ENDPOINT}/seats/`,
      { credentials: 'include', headers: this.header() },
    );
    return this._handleError(res);
  }

  async revoke(username) {
    const res = await fetch(
      `${this.constants.ENDPOINT}/revoke/`,
      {
        body: JSON.stringify({ username }),
        credentials: 'include',
        headers: {
          ...this.header(),
          'Content-Type': 'application/json',
        },
        method: 'POST',
      },
    );
    return this._handleError(res);
  }

  async reinstate(username) {
    const res = await fetch(
      `${this.constants.ENDPOINT}/reinstate/`,
      {
        body: JSON.stringify({ username }),
        credentials: 'include',
        headers: {
          ...this.header(),
          'Content-Type': 'application/json',
        },
        method: 'POST',
      },
    );
    return this._handleError(res);
  }

  async setRole(username, role) {
    const res = await fetch(
      `${this.constants.ENDPOINT}/set_role/`,
      {
        body: JSON.stringify({ role, username }),
        credentials: 'include',
        headers: {
          ...this.header(),
          'Content-Type': 'application/json',
        },
        method: 'POST',
      },
    );
    return this._handleError(res);
  }
}

export default new Seat();
