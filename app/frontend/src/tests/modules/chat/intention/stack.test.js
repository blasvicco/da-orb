// Libs imports
import { describe, expect, it } from 'vitest';

// App imports
import { buildIntentionTree, deriveIntentionNodes } from '@/modules/chat/intention/stack';

// Fixtures
const makeMessage = (state) => ({ state, text: 'hi', type: 'agent' });

describe('intentionStack.deriveIntentionNodes', () => {
  it.each([
    ['no messages at all', []],
    ['no message carries a state snapshot', [{ text: 'hi', type: 'user' }]],
    ['the latest state has no intention_nodes', [makeMessage({})]],
  ])('returns an empty list when %s', (_label, messages) => {
    expect(deriveIntentionNodes(messages)).toEqual([]);
  });

  it('falls back to the raw process_id when no process_definition name is present', () => {
    const nodes = deriveIntentionNodes([makeMessage({
      intention_nodes: { 'p1#0': { id: 'p1#0', parent_id: null, process_definition: null, process_id: 'purchase_request', status: 'active' } },
    })]);
    expect(nodes).toEqual([{
      id: 'p1#0', label: 'purchase_request', parentId: null, status: 'active', errorDetail: null,
    }]);
  });

  it('prefers the process_definition name over the raw process_id', () => {
    const nodes = deriveIntentionNodes([makeMessage({
      intention_nodes: {
        'p1#0': {
          id: 'p1#0', parent_id: null,
          process_definition: { name: 'Purchase Request' }, process_id: 'purchase_request', status: 'active',
        },
      },
    })]);
    expect(nodes[0].label).toBe('Purchase Request');
  });

  it('falls back to an empty label when the node carries neither a process_definition nor a process_id', () => {
    const nodes = deriveIntentionNodes([makeMessage({
      intention_nodes: { 'p1#0': { id: 'p1#0', parent_id: null, status: 'active' } },
    })]);
    expect(nodes[0].label).toBe('');
  });

  it('preserves intention_nodes insertion order and carries the parent_id chain through as parentId', () => {
    const nodes = deriveIntentionNodes([makeMessage({
      intention_nodes: {
        'pr#0': { id: 'pr#0', parent_id: null, process_definition: { name: 'Purchase Request' }, process_id: 'purchase_request', status: 'paused' },
        'si#1': { id: 'si#1', parent_id: 'pr#0', process_definition: null, process_id: 'search_items', status: 'paused' },
        'sig#2': { id: 'sig#2', parent_id: 'si#1', process_definition: null, process_id: 'search_item_groups', status: 'active' },
      },
    })]);
    expect(nodes.map((n) => [n.id, n.parentId, n.label, n.status])).toEqual([
      ['pr#0', null, 'Purchase Request', 'paused'],
      ['si#1', 'pr#0', 'search_items', 'paused'],
      ['sig#2', 'si#1', 'search_item_groups', 'active'],
    ]);
  });

  it('keeps completed/one-shot intentions visible instead of dropping them', () => {
    const nodes = deriveIntentionNodes([makeMessage({
      active_node_id: null,
      intention_nodes: {
        'list_deliveries#0': { id: 'list_deliveries#0', parent_id: null, process_definition: null, process_id: 'list_deliveries', status: 'completed' },
      },
    })]);
    expect(nodes).toEqual([{
      id: 'list_deliveries#0', label: 'list_deliveries', parentId: null, status: 'completed', errorDetail: null,
    }]);
  });

  it('passes error_detail through as errorDetail when present on the node', () => {
    const nodes = deriveIntentionNodes([makeMessage({
      intention_nodes: {
        'pr#0': { id: 'pr#0', parent_id: null, process_id: 'purchase_request', status: 'failed', error_detail: 'Required date is missing (1)' },
      },
    })]);
    expect(nodes[0].errorDetail).toBe('Required date is missing (1)');
  });

  it('defaults errorDetail to null when the node carries no error_detail', () => {
    const nodes = deriveIntentionNodes([makeMessage({
      intention_nodes: { 'pr#0': { id: 'pr#0', parent_id: null, process_id: 'purchase_request', status: 'active' } },
    })]);
    expect(nodes[0].errorDetail).toBeNull();
  });

  it('reflects only the most recent state snapshot, ignoring stale earlier messages', () => {
    const nodes = deriveIntentionNodes([
      makeMessage({ intention_nodes: { 'pr#0': { id: 'pr#0', parent_id: null, process_id: 'purchase_request', status: 'completed' } } }),
      makeMessage({ intention_nodes: { 'si#0': { id: 'si#0', parent_id: null, process_id: 'search_items', status: 'active' } } }),
    ]);
    expect(nodes).toEqual([{
      id: 'si#0', label: 'search_items', parentId: null, status: 'active', errorDetail: null,
    }]);
  });

  it('falls back to the session-level state when no message carries one (a reloaded session\'s history)', () => {
    const fallbackState = { intention_nodes: { 'pr#0': { id: 'pr#0', parent_id: null, process_id: 'purchase_request', status: 'completed' } } };
    const nodes = deriveIntentionNodes([{ text: 'hi', type: 'user' }, { text: 'hi', type: 'agent' }], fallbackState);
    expect(nodes).toEqual([{
      id: 'pr#0', label: 'purchase_request', parentId: null, status: 'completed', errorDetail: null,
    }]);
  });

  it('prefers a message-level state over the fallback session state when both are present', () => {
    const fallbackState = { intention_nodes: { 'stale#0': { id: 'stale#0', parent_id: null, process_id: 'stale', status: 'completed' } } };
    const nodes = deriveIntentionNodes(
      [makeMessage({ intention_nodes: { 'fresh#0': { id: 'fresh#0', parent_id: null, process_id: 'fresh', status: 'active' } } })],
      fallbackState,
    );
    expect(nodes).toEqual([{
      id: 'fresh#0', label: 'fresh', parentId: null, status: 'active', errorDetail: null,
    }]);
  });

  it('returns an empty list when there is neither a message state nor a fallback state', () => {
    expect(deriveIntentionNodes([{ text: 'hi', type: 'user' }], null)).toEqual([]);
  });
});

describe('intentionStack.buildIntentionTree', () => {
  it('returns an empty array for an empty node list', () => {
    expect(buildIntentionTree([])).toEqual([]);
  });

  it('nests a child under its parent using key/title/children', () => {
    const tree = buildIntentionTree([
      { id: 'pr#0', label: 'Purchase Request', parentId: null, status: 'paused' },
      { id: 'si#1', label: 'search_items', parentId: 'pr#0', status: 'active' },
    ]);
    expect(tree).toHaveLength(1);
    expect(tree[0]).toMatchObject({ key: 'pr#0', title: 'Purchase Request' });
    expect(tree[0].children).toHaveLength(1);
    expect(tree[0].children[0]).toMatchObject({ key: 'si#1', title: 'search_items', parentId: 'pr#0' });
  });

  it('treats siblings with the same parent as separate children of that parent', () => {
    const tree = buildIntentionTree([
      { id: 'pr#0', label: 'Purchase Request', parentId: null, status: 'paused' },
      { id: 'vendors#1', label: 'List Vendors', parentId: 'pr#0', status: 'completed' },
      { id: 'tax#2', label: 'List Tax Codes', parentId: 'pr#0', status: 'completed' },
    ]);
    expect(tree).toHaveLength(1);
    expect(tree[0].children.map((c) => c.key)).toEqual(['vendors#1', 'tax#2']);
  });

  it('treats a node whose parent is missing from the list as a root', () => {
    const tree = buildIntentionTree([
      { id: 'orphan#0', label: 'Orphan', parentId: 'missing-parent', status: 'active' },
    ]);
    expect(tree).toHaveLength(1);
    expect(tree[0].key).toBe('orphan#0');
  });

  it('supports multiple independent root nodes for sequential, non-diverged intentions', () => {
    const tree = buildIntentionTree([
      { id: 'a#0', label: 'A', parentId: null, status: 'completed' },
      { id: 'b#1', label: 'B', parentId: null, status: 'completed' },
    ]);
    expect(tree.map((n) => n.key)).toEqual(['a#0', 'b#1']);
  });
});
