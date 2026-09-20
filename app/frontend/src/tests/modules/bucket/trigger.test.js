// Libs imports
import { describe, expect, it } from 'vitest';

// App imports
import { formatFileSize } from '@/modules/bucket/trigger';

describe('formatFileSize', () => {
  it.each([
    ['zero bytes', 0, '0 B'],
    ['sub-KB byte count', 512, '512 B'],
    ['exact KB boundary', 1024, '1.0 KB'],
    ['fractional KB', 1536, '1.5 KB'],
    ['fractional MB', 1024 * 1024 * 2.5, '2.5 MB'],
    ['fractional GB', 1024 * 1024 * 1024 * 3, '3.0 GB'],
    ['non-numeric input defaults to 0', undefined, '0 B'],
  ])('%s -> formatFileSize(%s) returns %s', (_label, bytes, expected) => {
    expect(formatFileSize(bytes)).toBe(expected);
  });
});
