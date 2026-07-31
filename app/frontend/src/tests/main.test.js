// Libs imports
import { describe, expect, it, vi } from 'vitest';

// Mocks
const mockApp = vi.hoisted(() => {
  const app = { mount: vi.fn(), use: vi.fn() };
  app.use.mockReturnValue(app);
  return app;
});
const mockCreateApp = vi.hoisted(() => vi.fn(() => mockApp));
const mockCreatePinia = vi.hoisted(() => vi.fn(() => ({ __pinia: true })));

vi.mock('vue', async (importOriginal) => ({ ...(await importOriginal()), createApp: mockCreateApp }));
vi.mock('pinia', async (importOriginal) => ({ ...(await importOriginal()), createPinia: mockCreatePinia }));
vi.mock('@/app.vue', () => ({ default: { __mockApp: true } }));
vi.mock('@/i18n', () => ({ default: { __mockI18n: true } }));
vi.mock('@/router', () => ({ default: { __mockRouter: true } }));

describe('main entry point', () => {
  it('creates the root app and wires router, pinia, and i18n before mounting it', async () => {
    await import('@/main.js');

    expect(mockCreateApp).toHaveBeenCalledWith({ __mockApp: true });
    expect(mockApp.use).toHaveBeenCalledWith({ __mockRouter: true });
    expect(mockCreatePinia).toHaveBeenCalled();
    expect(mockApp.use).toHaveBeenCalledWith({ __pinia: true });
    expect(mockApp.use).toHaveBeenCalledWith({ __mockI18n: true });
    expect(mockApp.mount).toHaveBeenCalledWith('#app');
  });
});
