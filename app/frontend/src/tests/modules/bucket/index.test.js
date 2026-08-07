// Libs imports
import { beforeEach, describe, expect, it, vi } from 'vitest';

// Mocks
const mockBucket = vi.hoisted(() => ({
  deleteFile: vi.fn().mockResolvedValue({}),
  downloadUrl: vi.fn().mockResolvedValue({ url: '' }),
  files: vi.fn().mockResolvedValue([]),
  upload: vi.fn().mockResolvedValue({}),
}));

vi.mock('@/modules/api', () => ({ default: { Bucket: mockBucket } }));

// App imports
import { useBucket } from '@/modules/bucket';

// Fixtures
const makeFile = (name = 'orders.csv') => new File(['a,b'], name, { type: 'text/csv' });
const makeApiFile = (overrides = {}) => ({ id: 1, name: 'orders.csv', origin: 'user_upload', size: 2048, ...overrides });

describe('useBucket', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockBucket.deleteFile.mockResolvedValue({});
    mockBucket.files.mockResolvedValue([]);
    mockBucket.downloadUrl.mockResolvedValue({ url: '' });
    mockBucket.upload.mockResolvedValue({});
  });

  it('starts with empty files and pendingFiles', () => {
    const bucket = useBucket();
    expect(bucket.files).toEqual([]);
    expect(bucket.pendingFiles).toEqual([]);
  });

  describe('refreshFiles', () => {
    it('clears the list when there is no sessionId', async () => {
      const bucket = useBucket();
      await bucket.refreshFiles(null);
      expect(bucket.files).toEqual([]);
      expect(mockBucket.files).not.toHaveBeenCalled();
    });

    it('fetches and stores files for a sessionId', async () => {
      mockBucket.files.mockResolvedValue([makeApiFile()]);
      const bucket = useBucket();
      await bucket.refreshFiles(42);
      expect(mockBucket.files).toHaveBeenCalledWith(42);
      expect(bucket.files).toEqual([makeApiFile()]);
    });

    it('leaves the list untouched when the API errors', async () => {
      mockBucket.files.mockResolvedValue({ errors: [{ detail: 'boom' }] });
      const bucket = useBucket();
      await bucket.refreshFiles(42);
      expect(bucket.files).toEqual([]);
    });
  });

  describe('addFiles', () => {
    it('uploads immediately when a sessionId is present', async () => {
      const file = makeFile();
      mockBucket.files.mockResolvedValue([makeApiFile()]);
      const bucket = useBucket();

      await bucket.addFiles(42, [file]);

      expect(mockBucket.upload).toHaveBeenCalledWith(42, file);
      expect(bucket.files).toEqual([makeApiFile()]);
      expect(bucket.pendingFiles).toEqual([]);
    });

    it('stages files without uploading when there is no sessionId yet', async () => {
      const file = makeFile();
      const bucket = useBucket();

      await bucket.addFiles(null, [file]);

      expect(mockBucket.upload).not.toHaveBeenCalled();
      expect(bucket.pendingFiles).toEqual([file]);
    });

    it('does nothing for an empty file list', async () => {
      const bucket = useBucket();
      await bucket.addFiles(null, []);
      expect(bucket.pendingFiles).toEqual([]);
    });

    it('returns the uploaded file records when a sessionId is present', async () => {
      const file = makeFile();
      mockBucket.upload.mockResolvedValue(makeApiFile());
      mockBucket.files.mockResolvedValue([makeApiFile()]);
      const bucket = useBucket();

      const result = await bucket.addFiles(42, [file]);

      expect(result).toEqual([makeApiFile()]);
    });

    it('filters out failed uploads from the returned records', async () => {
      mockBucket.upload
        .mockResolvedValueOnce(makeApiFile({ id: 1 }))
        .mockResolvedValueOnce({ errors: [{ detail: 'boom' }] });
      const bucket = useBucket();

      const result = await bucket.addFiles(42, [makeFile('a.csv'), makeFile('b.csv')]);

      expect(result).toEqual([makeApiFile({ id: 1 })]);
    });

    it('returns an empty array when staging without a sessionId', async () => {
      const bucket = useBucket();
      const result = await bucket.addFiles(null, [makeFile()]);
      expect(result).toEqual([]);
    });

    it('accumulates multiple staged batches', async () => {
      const bucket = useBucket();
      await bucket.addFiles(null, [makeFile('a.csv')]);
      await bucket.addFiles(null, [makeFile('b.csv')]);
      expect(bucket.pendingFiles.map((entry) => entry.name)).toEqual(['a.csv', 'b.csv']);
    });
  });

  describe('setSessionId', () => {
    it('uploads and clears staged files once a real session id appears', async () => {
      const file = makeFile();
      mockBucket.files.mockResolvedValue([makeApiFile()]);
      const bucket = useBucket();
      await bucket.addFiles(null, [file]);

      await bucket.setSessionId(42);

      expect(mockBucket.upload).toHaveBeenCalledWith(42, file);
      expect(bucket.pendingFiles).toEqual([]);
      expect(bucket.files).toEqual([makeApiFile()]);
    });

    it('just refreshes the list when there are no staged files', async () => {
      mockBucket.files.mockResolvedValue([makeApiFile()]);
      const bucket = useBucket();

      await bucket.setSessionId(42);

      expect(mockBucket.upload).not.toHaveBeenCalled();
      expect(mockBucket.files).toHaveBeenCalledWith(42);
    });

    it('clears the list when the session id goes back to null', async () => {
      mockBucket.files.mockResolvedValue([makeApiFile()]);
      const bucket = useBucket();
      await bucket.setSessionId(42);
      expect(bucket.files).toEqual([makeApiFile()]);

      await bucket.setSessionId(null);
      expect(bucket.files).toEqual([]);
    });
  });

  describe('removePendingFile', () => {
    it('removes only the file at the given index', async () => {
      const bucket = useBucket();
      await bucket.addFiles(null, [makeFile('a.csv'), makeFile('b.csv'), makeFile('c.csv')]);

      bucket.removePendingFile(1);

      expect(bucket.pendingFiles.map((entry) => entry.name)).toEqual(['a.csv', 'c.csv']);
    });

    it('does nothing for an out-of-range index', async () => {
      const bucket = useBucket();
      await bucket.addFiles(null, [makeFile('a.csv')]);

      bucket.removePendingFile(5);

      expect(bucket.pendingFiles.map((entry) => entry.name)).toEqual(['a.csv']);
    });
  });

  describe('deleteFile', () => {
    it('removes the file from the list once the API confirms deletion', async () => {
      mockBucket.files.mockResolvedValue([makeApiFile({ id: 1 }), makeApiFile({ id: 2, name: 'b.csv' })]);
      const bucket = useBucket();
      await bucket.refreshFiles(42);

      await bucket.deleteFile(1);

      expect(mockBucket.deleteFile).toHaveBeenCalledWith(1);
      expect(bucket.files.map((file) => file.id)).toEqual([2]);
    });

    it('leaves the list untouched when the API errors', async () => {
      mockBucket.files.mockResolvedValue([makeApiFile({ id: 1 })]);
      mockBucket.deleteFile.mockResolvedValue({ errors: [{ detail: 'boom' }] });
      const bucket = useBucket();
      await bucket.refreshFiles(42);

      await bucket.deleteFile(1);

      expect(bucket.files.map((file) => file.id)).toEqual([1]);
    });
  });

  describe('downloadUrl', () => {
    it('delegates to the API', async () => {
      mockBucket.downloadUrl.mockResolvedValue({ url: 'https://signed.example/orders.csv' });
      const bucket = useBucket();
      const result = await bucket.downloadUrl(1);
      expect(mockBucket.downloadUrl).toHaveBeenCalledWith(1);
      expect(result).toEqual({ url: 'https://signed.example/orders.csv' });
    });
  });
});
