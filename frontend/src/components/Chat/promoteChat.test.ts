import { describe, it, expect } from 'vitest';
import {
  headerMode,
  shouldShowSaveButton,
  shouldShowNudge,
  composerFootnoteVariant,
  NUDGE_MIN_MESSAGES,
  type PromoteChatContext,
} from './promoteChat';

/** A free-form chat with a bit of history and no user activity this session. */
function ctx(overrides: Partial<PromoteChatContext> = {}): PromoteChatContext {
  return {
    inProject: false,
    hasMessages: true,
    messageCount: 6,
    isProcessing: false,
    userSentThisSession: false,
    nudgeDismissed: false,
    ...overrides,
  };
}

describe('headerMode', () => {
  it('is hidden for a brand-new chat (no messages)', () => {
    expect(headerMode(ctx({ hasMessages: false, messageCount: 0 }))).toBe('hidden');
  });

  it('is free-form for a free-form chat with messages', () => {
    expect(headerMode(ctx())).toBe('free-form');
  });

  it('is project when the chat is attached to a project', () => {
    expect(headerMode(ctx({ inProject: true }))).toBe('project');
  });

  it('stays hidden even in a project when there are no messages', () => {
    expect(
      headerMode(ctx({ inProject: true, hasMessages: false, messageCount: 0 })),
    ).toBe('hidden');
  });
});

describe('shouldShowSaveButton', () => {
  it('shows for a free-form, non-new chat', () => {
    expect(shouldShowSaveButton(ctx())).toBe(true);
  });

  it('hides for a brand-new chat', () => {
    expect(
      shouldShowSaveButton(ctx({ hasMessages: false, messageCount: 0 })),
    ).toBe(false);
  });

  it('hides once the chat is in a project', () => {
    expect(shouldShowSaveButton(ctx({ inProject: true }))).toBe(false);
  });
});

describe('shouldShowNudge', () => {
  it('shows for an idle free-form chat past the message threshold', () => {
    expect(shouldShowNudge(ctx({ messageCount: NUDGE_MIN_MESSAGES }))).toBe(true);
  });

  it('hides below the message threshold', () => {
    expect(shouldShowNudge(ctx({ messageCount: NUDGE_MIN_MESSAGES - 1 }))).toBe(
      false,
    );
  });

  it('hides while agents are generating', () => {
    expect(shouldShowNudge(ctx({ isProcessing: true }))).toBe(false);
  });

  it('hides after the user sends a message this session', () => {
    expect(shouldShowNudge(ctx({ userSentThisSession: true }))).toBe(false);
  });

  it('hides once dismissed', () => {
    expect(shouldShowNudge(ctx({ nudgeDismissed: true }))).toBe(false);
  });

  it('hides for a project chat', () => {
    expect(shouldShowNudge(ctx({ inProject: true }))).toBe(false);
  });
});

describe('composerFootnoteVariant', () => {
  it('is none when the chat is in a project', () => {
    expect(composerFootnoteVariant(ctx({ inProject: true }))).toBe('none');
  });

  it('is the short "new" variant for a brand-new free-form chat', () => {
    expect(
      composerFootnoteVariant(ctx({ hasMessages: false, messageCount: 0 })),
    ).toBe('new');
  });

  it('is the full (with-link) variant for a free-form chat with history', () => {
    expect(composerFootnoteVariant(ctx())).toBe('full');
  });
});
