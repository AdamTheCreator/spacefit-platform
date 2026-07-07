/**
 * Pure visibility logic for the "Save to project" (chat promotion) flow.
 *
 * Extracted from the components so the visibility conditions — header pill,
 * inline nudge, composer footnote — are unit-testable without a DOM. See
 * `promoteChat.test.ts`.
 */

export interface PromoteChatContext {
  /** Chat is attached to a project (either via route or after promotion). */
  inProject: boolean;
  /** At least one message exists — i.e. the chat is not brand-new. */
  hasMessages: boolean;
  /** Total message count (user + agent). Drives the nudge threshold. */
  messageCount: number;
  /** Agents are currently generating a reply. */
  isProcessing: boolean;
  /** The user has sent a message during this mount (session). */
  userSentThisSession: boolean;
  /** The nudge was dismissed this session. */
  nudgeDismissed: boolean;
}

/** Minimum messages before the promote nudge is worth showing. */
export const NUDGE_MIN_MESSAGES = 4;

export type HeaderMode = 'hidden' | 'project' | 'free-form';

/**
 * What the chat header should render:
 * - `hidden`    — brand-new chat (no messages), no header chrome.
 * - `project`   — an "In: {project}" pill, no promote button.
 * - `free-form` — a "Free-form" pill + the "Save to project" button.
 */
export function headerMode(ctx: PromoteChatContext): HeaderMode {
  if (!ctx.hasMessages) return 'hidden';
  return ctx.inProject ? 'project' : 'free-form';
}

/** The header "Save to project" button shows only for free-form, non-new chats. */
export function shouldShowSaveButton(ctx: PromoteChatContext): boolean {
  return headerMode(ctx) === 'free-form';
}

/**
 * The inline nudge banner shows when the chat is free-form, idle, has built up
 * some history, and the user hasn't picked the conversation back up this
 * session (nor dismissed the nudge).
 */
export function shouldShowNudge(ctx: PromoteChatContext): boolean {
  return (
    !ctx.inProject &&
    !ctx.isProcessing &&
    ctx.messageCount >= NUDGE_MIN_MESSAGES &&
    !ctx.userSentThisSession &&
    !ctx.nudgeDismissed
  );
}

export type FootnoteVariant = 'none' | 'new' | 'full';

/**
 * The composer footnote:
 * - `none` — in a project; project context applies, no footnote.
 * - `new`  — brand-new free-form chat; short "No project context." line.
 * - `full` — free-form chat with history; includes the "Save to project" link.
 */
export function composerFootnoteVariant(ctx: PromoteChatContext): FootnoteVariant {
  if (ctx.inProject) return 'none';
  if (!ctx.hasMessages) return 'new';
  return 'full';
}
