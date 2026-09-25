// Libs imports
import { describe, expect, it } from 'vitest';
import { defineComponent } from 'vue';

// App imports
import { mount } from '@/tests/helpers/mount';
import { useErrorText } from '@/modules/api/error-text';

// The composable reads the i18n instance, so it needs a real component's setup.
const errorTextFn = () => {
  let fn;
  mount(defineComponent({
    setup() {
      fn = useErrorText();
      return () => null;
    },
  }));
  return fn;
};

describe('useErrorText', () => {
  it.each([
    ['a detail with a translation', { attr: 'id', detail: 'Default project cannot be deleted.' }, 'The Default project cannot be deleted.'],
    ['an error with a null attr', { attr: null, detail: 'The destination project no longer exists.' }, 'The destination project no longer exists.'],
    ['a bulk-move validation error', { attr: 'session_ids', detail: 'Select at least one chat.' }, 'Select at least one chat.'],
    ['a detail nobody translated, falling back to its own text', { attr: 'summary', detail: 'Something odd.' }, 'Something odd.'],
    ['a hand-rolled { error } response', { error: 'MISSING_NAME' }, 'MISSING_NAME'],
    ['nothing to show', {}, 'ERROR'],
    ['no error at all', undefined, 'ERROR'],
  ])('turns %s into display text', (_label, error, expected) => {
    expect(errorTextFn()(error)).toBe(expected);
  });
});
