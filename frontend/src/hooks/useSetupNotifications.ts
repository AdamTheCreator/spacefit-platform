import { useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';
import { toast } from 'sonner';
import { useConnectorStatus } from './useConnectorHealth';

const DISMISS_PREFIX = 'sf_notif_dismiss_';
const TIP_PREFIX = 'sf_tip_seen_';

// Connector feature descriptions for user-friendly messages
const CONNECTOR_FEATURES: Record<string, string> = {
  costar: 'lease comps and tenant data',
  placer: 'foot traffic analytics',
  siteusa: 'vehicle traffic counts',
};

function isDismissed(key: string): boolean {
  return localStorage.getItem(`${DISMISS_PREFIX}${key}`) === '1';
}

function dismiss(key: string) {
  localStorage.setItem(`${DISMISS_PREFIX}${key}`, '1');
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
 *
 * Each notification is shown once per connector, ever.
 * Not shown when the user is already on the connections page.
 */
export function useSetupNotifications() {
  const { data: connectors } = useConnectorStatus();
  const hasShownRef = useRef(false);
  const location = useLocation();

  useEffect(() => {
    if (!connectors || hasShownRef.current) return;
    hasShownRef.current = true;

    // Don't show if user is already on the connections page
    if (location.pathname === '/connections') return;

    // Find disconnected or errored connectors not yet dismissed
    const disconnected = connectors.filter(
      (c) =>
        (c.connector_status === 'error' || c.connector_status === 'needs_reauth') &&
        !isDismissed(c.site_name),
    );

    if (disconnected.length === 0) return;

    // Show one notification then permanently dismiss it
    const toShow = disconnected[0];
    const feature = CONNECTOR_FEATURES[toShow.site_name.toLowerCase()] || 'premium data';
    const displayName = toShow.site_display_name || toShow.site_name;

    // Mark dismissed immediately so it never shows again
    dismiss(toShow.site_name);

    toast.info(`Connect ${displayName} to unlock ${feature}`, {
      duration: 8000,
      action: {
        label: 'Set up',
        onClick: () => {
          window.location.href = '/connections';
        },
      },
    });
  }, [connectors, location.pathname]);
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
