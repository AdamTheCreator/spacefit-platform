/**
 * Normalized BYOK error codes and user-facing messages.
 *
 * The backend's `app.byok.errors.BYOKError` serializes failures as
 * `{ error: "<code>", message: "<text>", ... }`. This module gives
 * the UI a single place to map those stable codes to:
 *   - a short, user-safe headline for the Settings cards
 *   - a longer body/fix hint
 *   - a boolean hinting whether a Retry / Revalidate button makes sense
 *
 * Keep this file in sync with backend `BYOKErrorCode` — tests on both
 * sides would catch drift, but the list is short enough to audit by eye.
 */

export type BYOKErrorCode =
  | 'credential_not_found'
  | 'credential_invalid'
  | 'credential_forbidden'
  | 'credential_rate_limited'
  | 'credential_quota_exceeded'
  | 'credential_decrypt_failed'
  | 'credential_duplicate'
  | 'model_not_allowed'
  | 'provider_server_error'
  | 'provider_timeout'
  | 'provider_unavailable'
  | 'invalid_request'
  | 'unsupported_provider';

export interface BYOKUserMessage {
  title: string;
  body: string;
  /**
   * `'revalidate'` → show "Revalidate key" CTA
   * `'retry'`      → show "Retry" button
   * `'wait'`       → show "Wait and retry" (for rate-limits)
   * `'none'`       → silent; message is informational only
   */
  action: 'revalidate' | 'retry' | 'wait' | 'none';
}

const DEFAULT_MESSAGES: Record<BYOKErrorCode, BYOKUserMessage> = {
  credential_not_found: {
    title: 'No API key configured',
    body: 'Add a key in the section below to use your own provider.',
    action: 'none',
  },
  credential_invalid: {
    title: 'Your API key was rejected',
    body: 'The provider returned an authentication error. The key may have been revoked or rotated at the provider — re-enter or validate the key to continue.',
    action: 'revalidate',
  },
  credential_forbidden: {
    title: "Your key can't access this model",
    body: "The provider recognised your key but your account doesn't have access to the requested model. Check your provider account's model access settings.",
    action: 'none',
  },
  credential_rate_limited: {
    title: 'Provider rate limit hit',
    body: "You're sending requests faster than your provider allows. Wait a moment and try again.",
    action: 'wait',
  },
  credential_quota_exceeded: {
    title: 'Monthly cap reached',
    body: 'This credential has hit its configured monthly request or spend cap. Raise the cap in the scope panel below or wait for the next period.',
    action: 'none',
  },
  credential_decrypt_failed: {
    title: 'Stored key could not be read',
    body: "We couldn't decrypt your stored key. Please re-enter it — nothing you typed before was exposed, just not recoverable.",
    action: 'revalidate',
  },
  credential_duplicate: {
    title: 'Key already on file',
    body: 'This exact key is already stored on your account. Use the existing entry or enter a different key.',
    action: 'none',
  },
  model_not_allowed: {
    title: "Model isn't allowed for this key",
    body: 'Your scope settings restrict this credential to a subset of models. Either pick an allowed model or adjust the scope panel below.',
    action: 'none',
  },
  provider_server_error: {
    title: "The provider's server had a problem",
    body: 'This is usually transient. Try again in a moment.',
    action: 'retry',
  },
  provider_timeout: {
    title: "The provider didn't respond in time",
    body: 'Your key and model are fine — the provider was slow. Retrying usually works.',
    action: 'retry',
  },
  provider_unavailable: {
    title: "Couldn't reach the provider",
    body: 'A network error prevented us from contacting the provider. Retry, or check the provider status page.',
    action: 'retry',
  },
  invalid_request: {
    title: 'Request was malformed',
    body: 'Please double-check the values you entered — something about the submission was rejected.',
    action: 'none',
  },
  unsupported_provider: {
    title: 'Provider is not supported',
    body: 'This provider is not in the current supported list.',
    action: 'none',
  },
};

/**
 * Normalize whatever axios / fetch error shape the request produced
 * into a stable UI message. Handles:
 *   - our backend's `{ error: "<code>", message, detail }` body
 *   - FastAPI's default `{ detail: "..." }` shape
 *   - network errors without a response at all
 */
export function toBYOKUserMessage(err: unknown): BYOKUserMessage {
  // Axios error with a response body.
  const anyErr = err as {
    response?: { data?: { error?: string; message?: string; detail?: unknown } };
    message?: string;
    code?: string;
  };

  const data = anyErr?.response?.data;
  const code = (data?.error as BYOKErrorCode | undefined) ?? undefined;

  if (code && code in DEFAULT_MESSAGES) {
    const base = DEFAULT_MESSAGES[code];
    // If the backend provided a more specific message, prefer it for
    // the body — the action stays based on the code.
    const body = typeof data?.message === 'string' && data.message ? data.message : base.body;
    return { ...base, body };
  }

  // Network error (no response) — most likely the backend is cold-starting.
  if (!anyErr?.response) {
    return {
      title: "Couldn't reach the server",
      body: 'The backend may be waking up — try again in a few seconds.',
      action: 'retry',
    };
  }

  // Fall back to the FastAPI `detail` if no normalized code.
  const detail = data?.detail;
  if (typeof detail === 'string') {
    return { title: 'Request failed', body: detail, action: 'retry' };
  }

  return {
    title: 'Request failed',
    body: anyErr.message || 'Unexpected error.',
    action: 'retry',
  };
}

/**
 * Pull the normalized error code off an axios error, or `null` if the
 * response doesn't carry one. Handy for conditional UI branches that
 * don't need the full message struct.
 */
export function extractBYOKErrorCode(err: unknown): BYOKErrorCode | null {
  const code = (err as { response?: { data?: { error?: string } } })?.response?.data?.error;
  return code && code in DEFAULT_MESSAGES ? (code as BYOKErrorCode) : null;
}
