import { useEffect, useRef } from 'react';
import { toast } from 'sonner';
import { useConnectorStatus } from './useConnectorHealth';

const DISMISS_PREFIX = 'sf_notif_dismiss_';
const TIP_PREFIX = 'sf_tip_seen_';
const DISMISS_DAYS = 7;

// Connector feature descriptions for user-friendly messages
const CONNECTOR_FEATURES: Record<string, string> = {
  costar: 'lease comps and tenant data',
  placer: 'foot traffic analytics',
  siteusa: 'vehicle traffic counts',
};

function isDismissed(key: string): boolean {
  const dismissedAt = localStorage.getItem(`${DISMISS_PREFIX}${key}`);
  if (!dismissedAt) return false;
  const daysSince = (Date.now() - parseInt(dismissedAt, 10)) / (1000 * 60 * 60 * 24);
  return daysSince < DISMISS_DAYS;
}

function dismiss(key: string) {
  localStorage.setItem(`${DISMISS_PREFIX}${key}`, Date.now().toString());
}

function isTipSeen(key: string): boolean {
  return localStorage.getItem(`${TIP_PREFIX}${key}`) === '1';
}

function markTipSeen(key: string) {
  localStorage.setItem(`${TIP_PREFIX}${key}`, '1');
}

/**
 * Shows setup notifications for disconnected integrations
 * and onboarding tips for new users.
 */
export function useSetupNotifications() {
  const { data: connectors } = useConnectorStatus();
  const hasShownRef = useRef(false);

  // Setup notifications for disconnected connectors
  useEffect(() => {
    if (!connectors || hasShownRef.current) return;
    hasShownRef.current = true;

    // Find disconnected or errored connectors
    const disconnected = connectors.filter(
      (c) => c.connector_status === 'error' || c.connector_status === 'needs_reauth'
    );

    // Show at most 1 notification to avoid spam
    const toShow = disconnected.find((c) => !isDismissed(c.site_name));
    if (toShow) {
      const feature = CONNECTOR_FEATURES[toShow.site_name.toLowerCase()] || 'premium data';
      const displayName = toShow.site_display_name || toShow.site_name;

      toast.info(`Connect ${displayName} to unlock ${feature}`, {
        duration: 8000,
        action: {
          label: 'Set up',
          onClick: () => {
            window.location.href = '/connections';
          },
        },
        onDismiss: () => dismiss(toShow.site_name),
      });
    }
  }, [connectors]);
}

/**
 * Show a one-time onboarding tip.
 * Call this from specific pages/components when a tip is relevant.
 */
export function showOnboardingTip(tipKey: string, message: string) {
  if (isTipSeen(tipKey)) return;
  markTipSeen(tipKey);

  toast.info(message, {
    duration: 6000,
  });
}
