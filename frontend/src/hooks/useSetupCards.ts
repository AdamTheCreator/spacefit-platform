import { useCallback, useMemo, useState } from 'react';
import api from '../lib/axios';
import { useAuthStore } from '../stores/authStore';
import { useAIConfig } from './useAIConfig';
import { usePreferences } from './usePreferences';
import { useConnectorStatus } from './useConnectorHealth';
import { useQuery } from '@tanstack/react-query';

export type SetupCardId =
  | 'verify_email'
  | 'byok_key'
  | 'preferences'
  | 'customers'
  | 'placer';

export interface SetupCard {
  id: SetupCardId;
  title: string;
  description: string;
  cta: string;
  href: string;
  tone?: 'default' | 'attention';
}

const DISMISS_PREFIX = 'sg_setup_card_';

function isDismissed(id: SetupCardId): boolean {
  if (typeof window === 'undefined') return false;
  return localStorage.getItem(`${DISMISS_PREFIX}${id}`) === '1';
}

function persistDismiss(id: SetupCardId) {
  if (typeof window === 'undefined') return;
  localStorage.setItem(`${DISMISS_PREFIX}${id}`, '1');
}

function useCustomersCount(): { count: number | undefined } {
  const { user } = useAuthStore();
  const { data } = useQuery({
    queryKey: ['customersCount', user?.id],
    queryFn: async () => {
      const { data } = await api.get<{ total: number }>('/customers?page=1&page_size=1');
      return data.total;
    },
    enabled: !!user,
    staleTime: 1000 * 60 * 5,
    retry: 1,
  });
  return { count: data };
}

/**
 * Derives the current set of setup tasks worth surfacing on the Dashboard.
 *
 * Each card has a real "done" criterion sourced from existing endpoints —
 * once the underlying condition flips to true (user configures BYOK,
 * fills in preferences, imports a customer list, etc.) the card disappears
 * on the next render. Dismissals are stored in localStorage per-browser.
 */
export function useSetupCards() {
  const { user } = useAuthStore();
  const { data: aiConfig } = useAIConfig();
  const { data: preferences } = usePreferences();
  const { data: connectors } = useConnectorStatus();
  const { count: customersCount } = useCustomersCount();

  const [dismissedTick, setDismissedTick] = useState(0);

  const dismiss = useCallback((id: SetupCardId) => {
    persistDismiss(id);
    setDismissedTick((n) => n + 1);
  }, []);

  const cards = useMemo<SetupCard[]>(() => {
    // `dismissedTick` participates so the memo re-runs when a card is
    // dismissed; the value itself isn't used inside.
    void dismissedTick;

    const all: SetupCard[] = [];

    if (user && user.email_verified === false) {
      all.push({
        id: 'verify_email',
        title: 'Verify your email',
        description: 'Confirm your address so we can send password resets and team invites.',
        cta: 'Resend email',
        href: '/profile',
        tone: 'attention',
      });
    }

    if (aiConfig && !aiConfig.is_key_valid) {
      all.push({
        id: 'byok_key',
        title: 'Bring your own AI key',
        description:
          'Add an Anthropic, OpenAI, or Gemini key for unlimited usage on your own billing.',
        cta: 'Open AI settings',
        href: '/settings',
      });
    }

    if (preferences && !preferences.role) {
      all.push({
        id: 'preferences',
        title: 'Tell us about your role',
        description: 'Your role and target markets help the goose crew tailor answers.',
        cta: 'Set preferences',
        href: '/settings',
      });
    }

    if (customersCount !== undefined && customersCount === 0) {
      all.push({
        id: 'customers',
        title: 'Import your customer list',
        description: 'Upload a CSV or Excel file to start matching tenants to properties.',
        cta: 'Import customers',
        href: '/customers',
      });
    }

    if (connectors) {
      const placer = connectors.find((c) => c.site_name.toLowerCase() === 'placer');
      if (placer && placer.connector_status !== 'connected') {
        all.push({
          id: 'placer',
          title: 'Connect Placer.ai',
          description: 'Pull foot traffic and trade-area data into your projects.',
          cta: 'Connect Placer',
          href: '/connections',
        });
      }
    }

    return all.filter((c) => !isDismissed(c.id));
  }, [user, aiConfig, preferences, connectors, customersCount, dismissedTick]);

  return { cards, dismiss };
}
