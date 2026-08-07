import Abstract from './abstract';

class Bucket extends Abstract {
  constructor() {
    super();
    this.resource = 'bucket';
    this._updateEndpoint();
  }

  async deleteFile(fileId) {
    const res = await fetch(
      `${this.constants.ENDPOINT}/delete_file/?file_id=${fileId}`,
      { credentials: 'include', headers: this.header(), method: 'DELETE' },
    );
    return this._handleError(res);
  }

  async downloadUrl(fileId) {
    const res = await fetch(
      `${this.constants.ENDPOINT}/download/?file_id=${fileId}`,
      { credentials: 'include', headers: this.header() },
    );
    return this._handleError(res);
  }

  async files(sessionId) {
    const res = await fetch(
      `${this.constants.ENDPOINT}/files/?session_id=${sessionId}`,
      { credentials: 'include', headers: this.header() },
    );
    return this._handleError(res);
  }

  async upload(sessionId, file) {
    const body = new FormData();
    body.append('session_id', sessionId);
    body.append('file', file);
    const res = await fetch(
      `${this.constants.ENDPOINT}/upload/`,
      {
        // No 'Content-Type' header: the browser sets the multipart boundary itself.
        body,
        credentials: 'include',
        headers: this.header(),
        method: 'POST',
      },
    );
    return this._handleError(res);
  }
}

export default new Bucket();
