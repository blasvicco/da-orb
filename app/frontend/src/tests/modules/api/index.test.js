// Libs imports
import { describe, expect, it } from 'vitest';

// App imports
import AppAPI from '@/modules/api';
import Auth from '@/modules/api/auth';
import Bucket from '@/modules/api/bucket';
import Chat from '@/modules/api/chat';
import ChatSession from '@/modules/api/chat-session';
import Context from '@/modules/api/context';
import DocumentTemplate from '@/modules/api/document-template';
import Project from '@/modules/api/project';
import Seat from '@/modules/api/seat';
import Usage from '@/modules/api/usage';

describe('AppAPI', () => {
  it('exposes every resource client under its own key', () => {
    expect(AppAPI).toEqual({ Auth, Bucket, Chat, ChatSession, Context, DocumentTemplate, Project, Seat, Usage });
  });
});
