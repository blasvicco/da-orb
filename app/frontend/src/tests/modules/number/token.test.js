// Libs imports
import { describe, expect, it } from 'vitest';

// App imports
import { formatCompactNumber } from '@/modules/number/token';

describe('token.formatCompactNumber', () => {
  it.each([
    ['a value under 1000 is returned as-is', 42, '42'],
    ['thousands are compacted with a k suffix', 1500, '1.5k'],
    ['a whole thousand drops the trailing .0', 2000, '2k'],
    ['millions are compacted with an M suffix', 2_500_000, '2.5M'],
  ])('%s', (_label, input, expected) => {
    expect(formatCompactNumber(input)).toBe(expected);
  });
});
