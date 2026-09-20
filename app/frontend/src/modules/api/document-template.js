import Abstract from './abstract';

class DocumentTemplate extends Abstract {
  constructor() {
    super();
    this.resource = 'document_template';
    this._updateEndpoint();
  }

  async templates(documentType) {
    const query = documentType ? `?document_type=${documentType}` : '';
    const res = await fetch(
      `${this.constants.ENDPOINT}/templates/${query}`,
      { credentials: 'include', headers: this.header() },
    );
    return this._handleError(res);
  }

  async upload(name, documentType, file, { businessPartnerRef, language } = {}) {
    const body = new FormData();
    body.append('name', name);
    body.append('document_type', documentType);
    body.append('file', file);
    body.append('business_partner_ref', businessPartnerRef || '');
    body.append('language', language || '');
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

  async update(templateId, {
    name, documentType, file, businessPartnerRef, language,
  } = {}) {
    const body = new FormData();
    body.append('template_id', templateId);
    if (name) body.append('name', name);
    if (documentType) body.append('document_type', documentType);
    if (file) body.append('file', file);
    // Always sent (even empty) so the admin can explicitly clear an override — see
    // update_template's own "presence, not truthiness" handling of these two fields.
    body.append('business_partner_ref', businessPartnerRef || '');
    body.append('language', language || '');
    const res = await fetch(
      `${this.constants.ENDPOINT}/update_template/`,
      {
        body,
        credentials: 'include',
        headers: this.header(),
        method: 'PATCH',
      },
    );
    return this._handleError(res);
  }

  async remove(templateId) {
    const res = await fetch(
      `${this.constants.ENDPOINT}/remove/?template_id=${templateId}`,
      { credentials: 'include', headers: this.header(), method: 'DELETE' },
    );
    return this._handleError(res);
  }

  async setDefault(templateId) {
    const res = await fetch(
      `${this.constants.ENDPOINT}/set_default/`,
      {
        body: JSON.stringify({ template_id: templateId }),
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

  // Returns a Blob (the rendered PDF) on success, or the parsed error shape on failure —
  // callers must branch on `result instanceof Blob` since there's no JSON body to inspect
  // on the success path.
  async preview(templateId, data) {
    const res = await fetch(
      `${this.constants.ENDPOINT}/preview/`,
      {
        body: JSON.stringify({ data, template_id: templateId }),
        credentials: 'include',
        headers: {
          ...this.header(),
          'Content-Type': 'application/json',
        },
        method: 'POST',
      },
    );
    if (res.ok) return res.blob();
    return this._handleError(res);
  }
}

export default new DocumentTemplate();
