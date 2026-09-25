// Libs imports
import { describe, expect, it } from 'vitest';

// App imports
import en from '@/i18n/lng/en.js';
import es from '@/i18n/lng/es.js';

// Fixtures
const leaves = (node, prefix = '') => Object.entries(node).flatMap(([key, value]) => (
  typeof value === 'object' ? leaves(value, `${prefix}${key}.`) : [[`${prefix}${key}`, value]]
));

const placeholders = (text) => [...text.matchAll(/\{(\w+)\}/g)].map((match) => match[1]).sort();

const enLeaves = leaves(en.landing);
const esLeaves = leaves(es.landing);

describe('Landing.copyParity', () => {
  it('defines the same keys in both languages', () => {
    expect(esLeaves.map(([path]) => path).sort()).toEqual(enLeaves.map(([path]) => path).sort());
  });

  it('has no empty strings in either language', () => {
    const empty = [...enLeaves, ...esLeaves].filter(([, text]) => text.trim() === '');

    expect(empty).toEqual([]);
  });

  it('uses the same interpolation placeholders for every key in both languages', () => {
    const esByPath = Object.fromEntries(esLeaves);
    const mismatched = enLeaves
      .filter(([path, text]) => placeholders(text).join() !== placeholders(esByPath[path]).join())
      .map(([path]) => path);

    expect(mismatched).toEqual([]);
  });
});
