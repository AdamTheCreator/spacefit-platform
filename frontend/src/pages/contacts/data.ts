/* Contacts — shared types + presentation helpers for the directory.
 *
 * Live data is fetched via `hooks/useContacts.ts`; this module holds only the
 * shared interfaces and pure formatting helpers (no mock rows). */

// Sector color palette for monogram fallbacks
export const sectorColor: Record<string, string> = {
  'Fast Casual': '#FF8A3D',
  'QSR': '#E5B85C',
  'Coffee': '#8A6417',
  'Fitness': '#3A5BA0',
  'Grocery': '#2F7A3B',
  'Beauty': '#C25E1F',
  'Apparel': '#0F1B2D',
  'Specialty Food': '#FF8A3D',
  'Better Burger': '#C25E1F',
  'Eyewear': '#3A5BA0',
  'Home': '#8A6417',
  'Health': '#2F7A3B',
};

export interface Company {
  id: string;
  name: string;
  sector: string;
  subsector: string;
  us_locations: number;
  is_expanding: boolean | null;
  target_markets: string[];
  sf_min: number;
  sf_max: number;
  website: string;
  enriched_days: number | null;
  // Presentation-only; derived from sector/name when absent.
  logo_bg?: string;
  logo_text?: string;
  notes: string;
}

export type VerificationStatus = 'verified' | 'unverified' | 'stale' | 'bounced';
export type ContactSource = 'apollo' | 'linkedin' | 'costar_import' | 'manual';

export interface Contact {
  id: string;
  company_id: string;
  first: string;
  last: string;
  role: string;
  email: string | null;
  phone: string | null;
  verif: VerificationStatus;
  last_verified_days: number | null;
  last_contacted_days: number | null;
  last_reply_days: number | null;
  source: ContactSource;
  linkedin: boolean;
  notes: string;
}

export type InteractionType = 'meeting' | 'note' | 'enrich' | 'email_in' | 'email_out';

export interface Interaction {
  id: string;
  contact_id: string;
  type: InteractionType;
  when_days: number;
  who: string;
  title?: string;
  summary: string;
}

// ---- Pure formatting helpers ----

export function contactFullName(c: Contact): string {
  return `${c.first} ${c.last}`.trim();
}

export function contactInitials(c: Contact): string {
  return `${(c.first || '?')[0]}${(c.last || '?')[0]}`.toUpperCase();
}

export function sectorBg(sector: string): string {
  return sectorColor[sector] || '#3A5BA0';
}

export const verifLabel: Record<
  VerificationStatus,
  { label: string; bg: string; fg: string; dot: string }
> = {
  verified:   { label: 'Verified',   bg: '#E3F1E5', fg: '#2F7A3B', dot: '#2F7A3B' },
  unverified: { label: 'Unverified', bg: '#F2F5F9', fg: '#596779', dot: '#A7ADB7' },
  stale:      { label: 'Stale',      bg: '#FBEFC8', fg: '#8A6417', dot: '#E5B85C' },
  bounced:    { label: 'Bounced',    bg: '#FCE3DA', fg: '#C25E1F', dot: '#C25E1F' },
};

export function sourceLabel(s: string): string {
  return (
    {
      apollo: 'Apollo',
      linkedin: 'LinkedIn',
      costar_import: 'CoStar import',
      manual: 'Manual',
    } as Record<string, string>
  )[s] || s;
}

export function formatRelDays(days: number | null | undefined): string {
  if (days === null || days === undefined) return '—';
  if (days === 0) return 'Today';
  if (days === 1) return 'Yesterday';
  if (days < 7) return `${days}d ago`;
  if (days < 30) return `${Math.round(days / 7)}w ago`;
  if (days < 365) return `${Math.round(days / 30)}mo ago`;
  return `${Math.round(days / 365)}y ago`;
}

export function formatSF(min: number, max: number): string {
  if (!min && !max) return '—';
  if (min && max) return `${(min / 1000).toFixed(1).replace(/\.0$/, '')}–${(max / 1000).toFixed(1).replace(/\.0$/, '')}K sf`;
  return `${((min || max) / 1000).toFixed(1).replace(/\.0$/, '')}K sf`;
}
