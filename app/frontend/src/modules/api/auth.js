import Abstract from './abstract';

class Auth extends Abstract {
  /**
   * Constructor
  **/
  constructor() {
    super();
    this.resource = 'auth';
    this._updateEndpoint();
  }

  /**
   * Exchange a refresh token for a new session (open_id only).
   * @param {string} token - the stored refresh token
   * @return {object} updated session dict
  **/
  async refresh(token) {
    const res = await fetch(
      `${this.constants.ENDPOINT}/refresh/`,
      {
        body: JSON.stringify({ token }),
        credentials: 'include',
        headers: {
          ...this.header(),
          'Content-Type': 'application/json',
        },
        method: 'POST',
      }
    );
    return this._handleError(res);
  }

  /**
   * Authenticate with SAP B1S username / password credentials.
   * @param {string} username
   * @param {string} password
   * @param {string} database - SAP CompanyDB (may be empty if pre-configured on the org)
   * @return {object} normalised session dict
  **/
  async login(username, password, database = '') {
    const res = await fetch(
      `${this.constants.ENDPOINT}/login/`,
      {
        body: JSON.stringify({ username, password, database }),
        credentials: 'include',
        headers: {
          ...this.header(),
          'Content-Type': 'application/json',
        },
        method: 'POST',
      }
    );
    return this._handleError(res);
  }
}

export default new Auth();
