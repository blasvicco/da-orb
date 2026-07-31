// Libs imports
import { describe, expect, it } from 'vitest';

// App imports
import AppAPI from '@/modules/api';
import Auth from '@/modules/api/auth';
import Chat from '@/modules/api/chat';
import Context from '@/modules/api/context';
import Seat from '@/modules/api/seat';
import Usage from '@/modules/api/usage';

describe('AppAPI', () => {
  it('exposes every resource client under its own key', () => {
    expect(AppAPI).toEqual({ Auth, Chat, Context, Seat, Usage });
  });
});
