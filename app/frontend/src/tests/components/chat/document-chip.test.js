// Libs imports
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// Mocks
const mockBucket = vi.hoisted(() => ({
  downloadUrl: vi.fn(),
}));

vi.mock('@/modules/api', () => ({ default: { Bucket: mockBucket } }));

// App imports
import { flushPromises, mount } from '@/tests/helpers/mount';
import DocumentChip from '@/components/chat/document-chip.vue';

// Fixtures
const ATTACHMENT = { id: 42, name: 'factura_1.pdf' };

const mountChip = () => mount(DocumentChip, { props: { attachment: ATTACHMENT } });

describe('DocumentChip.render', () => {
  it('shows the attachment name and a download button labelled for it', () => {
    const wrapper = mountChip();

    expect(wrapper.find('.orb-document-chip-name').text()).toBe('factura_1.pdf');
    expect(wrapper.find('.orb-document-chip-download-btn').attributes('title')).toBe('Download');
  });
});

describe('DocumentChip.handleDownload', () => {
  let openSpy;

  beforeEach(() => {
    vi.clearAllMocks();
    openSpy = vi.spyOn(window, 'open').mockImplementation(() => null);
  });

  afterEach(() => {
    openSpy.mockRestore();
  });

  it('asks for the attachment\'s download URL and opens it in a new tab', async () => {
    mockBucket.downloadUrl.mockResolvedValue({ url: 'https://files.example.com/factura_1.pdf' });
    const wrapper = mountChip();

    await wrapper.find('.orb-document-chip-download-btn').trigger('click');
    await flushPromises();

    expect(mockBucket.downloadUrl).toHaveBeenCalledWith(42);
    expect(openSpy).toHaveBeenCalledWith('https://files.example.com/factura_1.pdf', '_blank');
  });

  it.each([
    ['an empty result', {}],
    ['a blank url', { url: '' }],
    ['no result at all', undefined],
  ])('opens nothing when the API answers with %s', async (_label, result) => {
    mockBucket.downloadUrl.mockResolvedValue(result);
    const wrapper = mountChip();

    await wrapper.find('.orb-document-chip-download-btn').trigger('click');
    await flushPromises();

    expect(mockBucket.downloadUrl).toHaveBeenCalledWith(42);
    expect(openSpy).not.toHaveBeenCalled();
  });
});
