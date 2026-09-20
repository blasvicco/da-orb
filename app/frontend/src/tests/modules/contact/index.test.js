// Libs imports
import { describe, expect, it } from 'vitest';

// App imports
import { useContactModal } from '@/modules/contact';

describe('useContactModal', () => {
  it('starts closed', () => {
    const modal = useContactModal();
    expect(modal.isOpen).toBe(false);
  });

  it('open() sets isOpen to true', () => {
    const modal = useContactModal();
    modal.open();
    expect(modal.isOpen).toBe(true);
  });

  it('close() sets isOpen to false', () => {
    const modal = useContactModal();
    modal.open();
    modal.close();
    expect(modal.isOpen).toBe(false);
  });
});
