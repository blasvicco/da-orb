// Libs imports
import { UserManager, WebStorageStateStore } from 'oidc-client-ts';
import { defineStore } from 'pinia';
import { ref } from 'vue';

// App imports
import AppAPI from '@/modules/api';

const SESSION_KEY = 'orb_session';

const isSapReady = () =>
	typeof window !== 'undefined' && Boolean(window?.sap?.ushell?.Container);

export const useAuth = defineStore('auth', () => {
	const _error = ref(null);
	const _loading = ref(false);
	const _session = ref(null);
	let _TORefresh = null;

	const bootstrap = () => {
		if (_session.value) return;
		const stored = window.sessionStorage.getItem(SESSION_KEY);
		if (stored) {
			try {
				const payload = JSON.parse(stored);
				_session.value = payload;
				_scheduleRefresh(payload);
			} catch {
				_session.value = null;
			}
		}
	};

	// Called by landing page after backend redirect (with session payload)
	const callback = (payload) => {
		_session.value = payload;
		window.sessionStorage.setItem(SESSION_KEY, JSON.stringify(payload));
		_loading.value = false;
		_scheduleRefresh(payload);
	};

	const getError = () => {
		return _error.value;
	};

	const getSession = () => {
		bootstrap();
		return _session.value;
	};

	const hasSession = () => {
		bootstrap();
		return !!_session.value;
	};

	const isAdmin = () => {
		bootstrap();
		return _session.value?.role === 'admin';
	};

	const isLoading = () => {
		return _loading.value;
	};

	// Open ID — redirect to SAP identity provider
	const signin = async (context) => {
		_error.value = null;
		_loading.value = true;

		try {
			// SAP Fiori Launchpad shell path (embedded mode)
			if (isSapReady()) {
				window.sap.ushell.Container
					.getService('CrossApplicationNavigation')
					.toExternal({ target: { shellHash: '#' } });
				return;
			}

			// Standard OAuth 2.0 Authorization Code + PKCE flow
			// oidc-client-ts enables PKCE automatically
			const manager = new UserManager({
				authority: context['base_url'],
				// extraQueryParams: { },
				scope: context.scopes ?? 'openid profile email',
				userStore: new WebStorageStateStore({ store: window.sessionStorage }),
				'client_id': context['client_id'],
				'redirect_uri': `${AppAPI.Auth.constants.ENDPOINT}/callback/`,
				'response_type': 'code',
			});

			// Browser navigates away — execution stops here
			await manager.signinRedirect();

		} catch (err) {
			_error.value = err.message;
			_loading.value = false;
		}
	};

	// B1S — credential-based sign-in (no redirect)
	const signinWithCredentials = async ({ username, password, database = '' }) => {
		_error.value = null;
		_loading.value = true;

		try {
			const session = await AppAPI.Auth.login(username, password, database);

			if (!session || session.errors) {
				const msg = session?.errors?.[0]?.detail
					|| session?.errors?.[0]?.error
					|| 'B1S_AUTH_FAILED';
				throw new Error(msg);
			}

			_session.value = session;
			window.sessionStorage.setItem(SESSION_KEY, JSON.stringify(session));
			_scheduleRefresh(session);
		} catch (err) {
			_error.value = err.message;
		} finally {
			_loading.value = false;
		}
	};

	const signout = () => {
		if (_TORefresh) {
			clearTimeout(_TORefresh);
			_TORefresh = null;
		}
		_session.value = null;
		window.sessionStorage.removeItem(SESSION_KEY);
		window.location.href = '/';
	};

	const _refresh = async () => {
		const { refresh_token: refToken } = _session?.value || {};
		try {
			// _handleError already parses JSON — response is a plain object, not a Response
			const newSession = await AppAPI.Auth.refresh(refToken);
			if (!newSession || newSession.errors) {
				throw new Error('Failed to refresh token.');
			}
			_session.value = newSession;
			window.sessionStorage.setItem(SESSION_KEY, JSON.stringify(newSession));
			_scheduleRefresh(newSession);
		} catch (error) {
			console.error('Auto-refresh token failed:', error);
			signout();
		}
	};

	const _scheduleRefresh = (session) => {
		if (_TORefresh) clearTimeout(_TORefresh);
		const { expires_at: expAt, refresh_token: refToken } = session;
		// B1S sessions have no refresh token — skip scheduling
		if (expAt && refToken) {
			const now = Math.floor(Date.now() / 1000);
			const secondsToExpiry = expAt - now;
			// Refresh 5 minutes (300 seconds) before expiry
			const secondsToRefresh = (secondsToExpiry - 300) * 1000;
			if (secondsToRefresh <= 0) return _refresh();
			_TORefresh = setTimeout(_refresh, secondsToRefresh);
		}
	};

	return {
		callback,
		hasSession,
		isAdmin,
		isLoading,
		getError,
		getSession,
		signin,
		signinWithCredentials,
		signout,
	};
});
