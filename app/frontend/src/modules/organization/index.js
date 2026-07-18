// Libs imports
import { defineStore } from 'pinia';
import { ref } from 'vue';

// App imports
import AppAPI from '@/modules/api';

export const useOrganization = defineStore('organization', () => {
	const _context = ref({});
	// null = not yet resolved, true = tenant org found, false = no org (bare domain)
	const _hasOrganization = ref(null);
	let _fetchPromise = null;

	const load = () => {
		if (_fetchPromise) return _fetchPromise;

		_fetchPromise = AppAPI.Context.get()
			.then((response) => {
				if (response?.errors) {
					_context.value = {};
					_hasOrganization.value = false;
				} else {
					_context.value = response;
					_hasOrganization.value = true;
				}
			})
			.catch(() => {
				// Network failure (backend unreachable) — leave hasOrganization as null (unknown)
				// rather than false, so an existing tenant isn't mistaken for the sign-up flow.
			});

		return _fetchPromise;
	};

	const getContext = () => _context.value;

	const hasOrganization = () => _hasOrganization.value;

	return {
		getContext,
		hasOrganization,
		load,
	};
});
