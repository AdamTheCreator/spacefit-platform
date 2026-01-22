export type SubscriptionTier = 'free' | 'pro' | 'enterprise';

export type SubscriptionStatus = 'active' | 'canceled' | 'past_due' | 'trialing' | 'paused';

export interface Plan {
  id: string;
  tier: SubscriptionTier;
  name: string;
  description: string | null;
  price_monthly: number;
  chat_sessions_per_month: number;
  void_analyses_per_month: number;
  demographics_reports_per_month: number;
  emails_per_month: number;
  documents_per_month: number;
  team_members: number;
  has_placer_access: boolean;
  has_siteusa_access: boolean;
  has_costar_access: boolean;
  has_email_outreach: boolean;
  has_api_access: boolean;
}

export interface Subscription {
  id: string;
  tier: SubscriptionTier;
  status: SubscriptionStatus;
  plan: Plan;
  current_period_start: string | null;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
}

export interface Usage {
  chat_session: number;
  void_analysis: number;
  demographics_report: number;
  email_sent: number;
  document_parsed: number;
}

export interface SubscriptionWithUsage {
  subscription: Subscription;
  usage: Usage;
  limits: Usage;
}

export interface CheckoutRequest {
  tier: SubscriptionTier;
  success_url: string;
  cancel_url: string;
}

export interface CheckoutResponse {
  checkout_url: string;
}

export interface PortalResponse {
  portal_url: string;
}

export interface StripeConfig {
  publishable_key: string;
}
