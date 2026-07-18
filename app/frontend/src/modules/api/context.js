import Abstract from './abstract';

class Context extends Abstract {
	/**
	 * Constructor
	**/
	constructor() {
		super();
		this.resource = 'context';
		this._updateEndpoint();
	}

	async get() {
		const res = await fetch(
			`${this.constants.ENDPOINT}/get/`,
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
}

export default new Context();
