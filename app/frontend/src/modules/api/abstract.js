// App imports
import { useAuth } from '@/modules/auth';

// Constants
window.BASE_API_URL = window.location.origin.replace(':5173', '');

export default class Abstract {
  /**
   * Constructor
  **/
  constructor() {
    const err = {
      100: 'Cannot instantiate an abstract class.',
    };

    if (new.target === Abstract) {
      throw new TypeError(err[100]);
    }

    this.constants = {
      API_URL: `${window.BASE_API_URL}/api`,
      VERSION: 'v1',
    };

  }

  /**
   * helper to calculate the basic oauth header
   * @param {void}
   * @return {void}
  **/
  header() {
    const auth = useAuth();
    const session = auth.getSession() || {};
    return {
      'Authorization': session.access_token ? `Bearer ${session.access_token}` : '',
      'X-SAP-Username': session.user?.username || '',
    };
  }

  /**
   * Hit DELETE {this.constants.ENDPOINT}/{id}
   * @param {integer} id of the resource
   * @return {object}
  **/
  async delete(id) {
    const res = await fetch(
      `${this.constants.ENDPOINT}/${id}/`,
      {
        credentials: 'include',
        headers: {
          ...this.header(),
          'Content-Type': 'application/json',
        },
        method: 'DELETE',
      }
    );
    return this._handleError(res);
  }

  /**
   * Hit GET {this.constants.ENDPOINT}/
   * to get object
   * @param {void}
   * @return {array}
  **/
  async get(id) {
    const res = await fetch(
      `${this.constants.ENDPOINT}/${id}/`,
      {
        credentials: 'include',
        headers: {
          ...this.header(),
          'Content-Type': 'application/json',
        },
        method: 'GET',
      }
    );
    return this._handleError(res);
  }

  /**
   * Hit GET {this.constants.ENDPOINT}/
   * to list objects
   * @param {void}
   * @return {array}
  **/
  async list(opts) {
    const { filters, limit, offset, sorter } = {
      filters: {},
      limit: 20,
      offset: 0,
      sorter: undefined,
      ...opts
    };
    // build filters
    let fQuery = Object.keys(filters).reduce((fQuery, field) => {
      return filters[field]
        ? `${fQuery}${field}=${filters[field]}&`
        : fQuery;
    }, '');
    // build sort
    fQuery += sorter?.field
      ? `ordering=${sorter.order === 'ascend' ? '' : '-'}${sorter.field}`
      : '';
    const res = await fetch(
      `${this.constants.ENDPOINT}/?limit=${limit}&offset=${offset}&${fQuery}`,
      {
        credentials: 'include',
        headers: {
          ...this.header(),
          'Content-Type': 'application/json',
        },
        method: 'GET',
      }
    );
    return this._handleError(res);
  }

  /**
   * Hit PUT/POST {this.constants.ENDPOINT}/{id}
   * to save obj detail
   * @param {object} obj detail
   * @return {object}
  **/
  async save(obj) {
    let method = 'POST';
    let url = `${this.constants.ENDPOINT}/`;
    if (obj.id) {
      method = 'PATCH';
      url += `${obj.id}/`
      delete (obj.id);
    }
    const res = await fetch(
      url,
      {
        method,
        body: JSON.stringify(obj),
        credentials: 'include',
        headers: {
          ...this.header(),
          'Content-Type': 'application/json',
        },
      }
    );
    return this._handleError(res);
  }

  /**
   * Protected function to handle any error response
   * @param {object} res from an api request
   * @return {object}
  **/
  async _handleError(res) {
    if ([200, 201, 202].includes(res.status)) {
      try {
        return await res.json();
      } catch {
        return {};
      }
    } else if (res.status === 204) { // DELETE request
      return { errors: false };
    }

    if (res.status == 401) {
      // TODO: Expire session and redirect to login
    }

    try {
      const response = await res.json();
      if (response.error) {
        return { errors: [response] };
      }
      return response;
    } catch {
      return { errors: [{ attr: null, detail: 'UKNOWN_ERROR' }] };
    }
  }

  /**
   * Helper to update the endpoint if base api url changed
   * @param {void}
   * @return {void}
  **/
  _updateEndpoint() {
    this.constants.ENDPOINT = `${this.constants.API_URL}/${this.constants.VERSION}/${this.resource}`;
  }
}
