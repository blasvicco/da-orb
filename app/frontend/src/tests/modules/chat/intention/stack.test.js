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
      intention_nodes: [{ id: 'p1#0', parent_id: null, process_definition: null, process_id: 'purchase_request', status: 'active' }],
    })]);
    expect(nodes).toEqual([{ id: 'p1#0', label: 'purchase_request', parentId: null, resumable: false, status: 'active' }]);
  });

  it('prefers the process_definition name over the raw process_id', () => {
    const nodes = deriveIntentionNodes([makeMessage({
      intention_nodes: [{
        id: 'p1#0', parent_id: null,
        process_definition: { name: 'Purchase Request' }, process_id: 'purchase_request', status: 'active',
      }],
    })]);
    expect(nodes[0].label).toBe('Purchase Request');
  });

  it('preserves intention_nodes order and carries the parent_id chain through as parentId', () => {
    const nodes = deriveIntentionNodes([makeMessage({
      intention_nodes: [
        { id: 'pr#0', parent_id: null, process_definition: { name: 'Purchase Request' }, process_id: 'purchase_request', status: 'paused' },
        { id: 'si#1', parent_id: 'pr#0', process_definition: null, process_id: 'search_items', status: 'paused' },
        { id: 'sig#2', parent_id: 'si#1', process_definition: null, process_id: 'search_item_groups', status: 'active' },
      ],
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
      intention_nodes: [
        { id: 'list_deliveries#0', parent_id: null, process_definition: null, process_id: 'list_deliveries', status: 'completed' },
      ],
    })]);
    expect(nodes).toEqual([{ id: 'list_deliveries#0', label: 'list_deliveries', parentId: null, resumable: false, status: 'completed' }]);
  });

  it('marks only the node at the top of paused_node_ids as resumable when awaiting_stack_resume is true', () => {
    const nodes = deriveIntentionNodes([makeMessage({
      awaiting_stack_resume: true,
      intention_nodes: [
        { id: 'pr#0', parent_id: null, process_id: 'purchase_request', status: 'paused' },
        { id: 'si#1', parent_id: 'pr#0', process_id: 'search_items', status: 'paused' },
      ],
      paused_node_ids: ['pr#0', 'si#1'],
    })]);
    expect(nodes.map((node) => node.resumable)).toEqual([false, true]);
  });

  it.each([
    ['awaiting_stack_resume is false', false],
    ['awaiting_stack_resume is absent', undefined],
    ['paused_node_ids is empty', true],
  ])('marks nothing resumable when %s', (label, awaitingStackResume) => {
    const pausedNodeIds = label === 'paused_node_ids is empty' ? [] : ['n0'];
    const nodes = deriveIntentionNodes([makeMessage({
      awaiting_stack_resume: awaitingStackResume,
      intention_nodes: [{ id: 'n0', parent_id: null, process_id: 'p', status: 'paused' }],
      paused_node_ids: pausedNodeIds,
    })]);
    expect(nodes.every((node) => node.resumable === false)).toBe(true);
  });

  it('reflects only the most recent state snapshot, ignoring stale earlier messages', () => {
    const nodes = deriveIntentionNodes([
      makeMessage({ intention_nodes: [{ id: 'pr#0', parent_id: null, process_id: 'purchase_request', status: 'completed' }] }),
      makeMessage({ intention_nodes: [{ id: 'si#0', parent_id: null, process_id: 'search_items', status: 'active' }] }),
    ]);
    expect(nodes).toEqual([{ id: 'si#0', label: 'search_items', parentId: null, resumable: false, status: 'active' }]);
  });

  it('falls back to the session-level state when no message carries one (a reloaded session\'s history)', () => {
    const fallbackState = { intention_nodes: [{ id: 'pr#0', parent_id: null, process_id: 'purchase_request', status: 'completed' }] };
    const nodes = deriveIntentionNodes([{ text: 'hi', type: 'user' }, { text: 'hi', type: 'agent' }], fallbackState);
    expect(nodes).toEqual([{ id: 'pr#0', label: 'purchase_request', parentId: null, resumable: false, status: 'completed' }]);
  });

  it('prefers a message-level state over the fallback session state when both are present', () => {
    const fallbackState = { intention_nodes: [{ id: 'stale#0', parent_id: null, process_id: 'stale', status: 'completed' }] };
    const nodes = deriveIntentionNodes(
      [makeMessage({ intention_nodes: [{ id: 'fresh#0', parent_id: null, process_id: 'fresh', status: 'active' }] })],
      fallbackState,
    );
    expect(nodes).toEqual([{ id: 'fresh#0', label: 'fresh', parentId: null, resumable: false, status: 'active' }]);
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
      { id: 'pr#0', label: 'Purchase Request', parentId: null, resumable: false, status: 'paused' },
      { id: 'si#1', label: 'search_items', parentId: 'pr#0', resumable: false, status: 'active' },
    ]);
    expect(tree).toHaveLength(1);
    expect(tree[0]).toMatchObject({ key: 'pr#0', title: 'Purchase Request' });
    expect(tree[0].children).toHaveLength(1);
    expect(tree[0].children[0]).toMatchObject({ key: 'si#1', title: 'search_items', parentId: 'pr#0' });
  });

  it('treats siblings with the same parent as separate children of that parent', () => {
    const tree = buildIntentionTree([
      { id: 'pr#0', label: 'Purchase Request', parentId: null, resumable: false, status: 'paused' },
      { id: 'vendors#1', label: 'List Vendors', parentId: 'pr#0', resumable: false, status: 'completed' },
      { id: 'tax#2', label: 'List Tax Codes', parentId: 'pr#0', resumable: false, status: 'completed' },
    ]);
    expect(tree).toHaveLength(1);
    expect(tree[0].children.map((c) => c.key)).toEqual(['vendors#1', 'tax#2']);
  });

  it('treats a node whose parent is missing from the list as a root', () => {
    const tree = buildIntentionTree([
      { id: 'orphan#0', label: 'Orphan', parentId: 'missing-parent', resumable: false, status: 'active' },
    ]);
    expect(tree).toHaveLength(1);
    expect(tree[0].key).toBe('orphan#0');
  });

  it('supports multiple independent root nodes for sequential, non-diverged intentions', () => {
    const tree = buildIntentionTree([
      { id: 'a#0', label: 'A', parentId: null, resumable: false, status: 'completed' },
      { id: 'b#1', label: 'B', parentId: null, resumable: false, status: 'completed' },
    ]);
    expect(tree.map((n) => n.key)).toEqual(['a#0', 'b#1']);
  });
});
