import Abstract from './abstract';

// list()/get()/save()/delete() are inherited from Abstract: they already speak the
// {filters, sorter, limit, offset} <-> {count, results} contract VSProject serves.
class Project extends Abstract {
  constructor() {
    super();
    this.resource = 'project';
    this._updateEndpoint();
  }

  async default() {
    const res = await fetch(
      `${this.constants.ENDPOINT}/default/`,
      { credentials: 'include', headers: this.header() },
    );
    return this._handleError(res);
  }

  async empty(id) {
    const res = await fetch(
      `${this.constants.ENDPOINT}/${id}/empty/`,
      { credentials: 'include', headers: this.header(), method: 'POST' },
    );
    return this._handleError(res);
  }

  async select(id) {
    const res = await fetch(
      `${this.constants.ENDPOINT}/${id}/select/`,
      { credentials: 'include', headers: this.header(), method: 'POST' },
    );
    return this._handleError(res);
  }
}

export default new Project();
