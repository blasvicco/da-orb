// Libs imports
import { defineStore } from 'pinia';
import { ref } from 'vue';

export const useContactModal = defineStore('contactModal', () => {
	const isOpen = ref(false);

	const close = () => {
		isOpen.value = false;
	};

	const open = () => {
		isOpen.value = true;
	};

	return {
		close,
		isOpen,
		open,
	};
});
