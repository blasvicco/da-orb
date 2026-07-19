import Abstract from './abstract';

class Usage extends Abstract {
  constructor() {
    super();
    this.resource = 'usage';
    this._updateEndpoint();
  }

  async summary() {
    const res = await fetch(
      `${this.constants.ENDPOINT}/summary/`,
      { credentials: 'include', headers: this.header() },
    );
    return this._handleError(res);
  }
}

export default new Usage();
