import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Check, Loader2 } from 'lucide-react';
import api from '../lib/axios';
import type {
  BillingInterval,
  Plan,
  SubscriptionTier,
  SubscriptionWithUsage,
} from '../types/subscription';
import { useAuthStore } from '../stores/authStore';
import { SalesLeadModal } from '../components/Pricing/SalesLeadModal';

const NAV_COLOR = '#0F1B2D';
const MUTED = '#737169';
const ACCENT = '#3A5BA0';
const BORDER = '#E0DFDD';
const BG = '#F8F8F7';

const TIER_ORDER: SubscriptionTier[] = ['free', 'starter', 'pro', 'max'];

const TIER_TAGLINES: Record<string, string> = {
  free: 'Try Space Goose with your own API key',
  starter: 'For solo brokers kicking the tires',
  pro: 'For active CRE pros who chat all day',
  max: 'For high-volume teams who live in chat',
};

const PER_TIER_HIGHLIGHTS: Record<string, string[]> = {
  free: [
    '10 chat sessions / month',
    '50 chat sessions / month with BYOK',
    '500K monthly token budget',
    'Bring your own OpenAI / Anthropic / Gemini key',
  ],
  starter: [
    'Everything in Free',
    '200 chat sessions / month',
    '2M monthly token budget',
    'Email outreach',
  ],
  pro: [
    'Everything in Starter',
    '1,000 chat sessions / month',
    '10M monthly token budget',
    'Placer.ai + SiteUSA built-in',
    'Pipeline reports',
  ],
  max: [
    'Everything in Pro',
    '5,000 chat sessions / month',
    '25M monthly token budget',
    'CoStar access',
    'API access',
  ],
};

export function PricingPage() {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuthStore();
  const [plans, setPlans] = useState<Plan[]>([]);
  const [currentSubscription, setCurrentSubscription] =
    useState<SubscriptionWithUsage | null>(null);
  const [loading, setLoading] = useState(true);
  const [checkoutLoading, setCheckoutLoading] = useState<string | null>(null);
  const [interval, setInterval] = useState<BillingInterval>('monthly');
  const [showSalesModal, setShowSalesModal] = useState(false);

  useEffect(() => {
    async function fetchData() {
      try {
        const plansResponse = await api.get<Plan[]>('/subscription/plans');
        setPlans(plansResponse.data);
        if (isAuthenticated) {
          const subResponse = await api.get<SubscriptionWithUsage>(
            '/subscription/current',
          );
          setCurrentSubscription(subResponse.data);
        }
      } catch (e) {
        console.error('Failed to fetch pricing data', e);
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, [isAuthenticated]);

  const planMap = useMemo(() => {
    const map = new Map<SubscriptionTier, Plan>();
    plans.forEach((p) => map.set(p.tier, p));
    return map;
  }, [plans]);

  const handleCheckout = async (tier: SubscriptionTier) => {
    if (!isAuthenticated) {
      navigate('/register', { state: { from: '/pricing', tier } });
      return;
    }
    if (tier === 'free') return;
    setCheckoutLoading(tier);
    try {
      const res = await api.post<{ checkout_url: string }>(
        '/billing/checkout',
        {
          tier,
          interval,
          success_url: `${window.location.origin}/settings?checkout=success`,
          cancel_url: `${window.location.origin}/pricing?checkout=canceled`,
        },
      );
      window.location.href = res.data.checkout_url;
    } catch (e) {
      console.error('Checkout failed', e);
      setCheckoutLoading(null);
    }
  };

  if (loading) {
    return (
      <div
        className="min-h-screen flex items-center justify-center"
        style={{ background: BG }}
      >
        <Loader2 size={28} className="animate-spin" style={{ color: ACCENT }} />
      </div>
    );
  }

  const currentTier = (currentSubscription?.subscription.tier ??
    'free') as SubscriptionTier;

  return (
    <div
      className="min-h-screen py-16 px-4"
      style={{
        background: BG,
        color: NAV_COLOR,
        fontFamily: 'var(--font-sans, Inter, system-ui, sans-serif)',
      }}
    >
      <div className="max-w-6xl mx-auto">
        <header className="text-center mb-10">
          <p
            className="text-xs font-semibold tracking-[0.2em] uppercase mb-3"
            style={{ color: ACCENT }}
          >
            Pricing
          </p>
          <h1
            className="text-4xl font-bold tracking-tight mb-3"
            style={{ fontFamily: "'Sora', sans-serif" }}
          >
            Built for individuals. Priced for teams.
          </h1>
          <p className="text-base max-w-xl mx-auto" style={{ color: MUTED }}>
            Start free with your own API key. Upgrade for higher limits and
            built-in data partners. Save 20% with annual billing.
          </p>
        </header>

        <BillingToggle interval={interval} onChange={setInterval} />

        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4 mb-12">
          {TIER_ORDER.map((tier) => {
            const plan = planMap.get(tier);
            if (!plan) return null;
            return (
              <PlanCard
                key={tier}
                plan={plan}
                interval={interval}
                isCurrent={currentTier === tier}
                isPopular={tier === 'pro'}
                onSelect={() => handleCheckout(tier)}
                loading={checkoutLoading === tier}
              />
            );
          })}
        </div>

        <EnterpriseCard onTalkToSales={() => setShowSalesModal(true)} />

        {currentSubscription && (
          <UsageSummary subscription={currentSubscription} />
        )}
      </div>

      <SalesLeadModal
        open={showSalesModal}
        onClose={() => setShowSalesModal(false)}
      />
    </div>
  );
}

function BillingToggle({
  interval,
  onChange,
}: {
  interval: BillingInterval;
  onChange: (i: BillingInterval) => void;
}) {
  return (
    <div className="flex items-center justify-center mb-10">
      <div
        className="inline-flex p-1 rounded-full border"
        style={{ borderColor: BORDER, background: 'white' }}
      >
        {(['monthly', 'yearly'] as const).map((opt) => {
          const active = interval === opt;
          return (
            <button
              key={opt}
              type="button"
              onClick={() => onChange(opt)}
              className="px-4 py-1.5 rounded-full text-sm font-medium transition inline-flex items-center gap-2"
              style={{
                background: active ? NAV_COLOR : 'transparent',
                color: active ? 'white' : MUTED,
              }}
            >
              {opt === 'monthly' ? 'Monthly' : 'Yearly'}
              {opt === 'yearly' && (
                <span
                  className="text-[10px] font-semibold tracking-wide uppercase px-1.5 py-0.5 rounded-full"
                  style={{
                    background: active ? '#E5A840' : '#FFF4D6',
                    color: active ? NAV_COLOR : '#7C5A12',
                  }}
                >
                  Save 20%
                </span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function PlanCard({
  plan,
  interval,
  isCurrent,
  isPopular,
  onSelect,
  loading,
}: {
  plan: Plan;
  interval: BillingInterval;
  isCurrent: boolean;
  isPopular: boolean;
  onSelect: () => void;
  loading: boolean;
}) {
  const highlights = PER_TIER_HIGHLIGHTS[plan.tier] ?? [];
  const tagline = TIER_TAGLINES[plan.tier] ?? plan.description ?? '';

  // Yearly column shows the monthly-equivalent price for comparability;
  // total billed annually is annotated under the price line.
  const monthlyDisplayCents =
    interval === 'yearly' && plan.price_yearly > 0
      ? Math.round(plan.price_yearly / 12)
      : plan.price_monthly;

  const isFree = plan.tier === 'free';
  const canCheckout =
    !isFree &&
    !isCurrent &&
    (interval === 'monthly' || plan.price_yearly > 0) &&
    plan.is_purchasable;

  return (
    <div
      className="relative rounded-2xl border bg-white p-6 flex flex-col"
      style={{
        borderColor: isPopular ? ACCENT : BORDER,
        boxShadow: isPopular
          ? '0 6px 24px rgba(58, 91, 160, 0.12)'
          : '0 1px 3px rgba(0,0,0,0.04)',
      }}
    >
      {isPopular && (
        <div className="absolute -top-3 left-6">
          <span
            className="text-[10px] font-semibold tracking-wide uppercase px-2.5 py-1 rounded-full"
            style={{ background: ACCENT, color: 'white' }}
          >
            Most popular
          </span>
        </div>
      )}

      <h2
        className="text-lg font-semibold mb-1"
        style={{ fontFamily: "'Sora', sans-serif", color: NAV_COLOR }}
      >
        {plan.name}
      </h2>
      <p className="text-xs mb-4 min-h-[2.5rem]" style={{ color: MUTED }}>
        {tagline}
      </p>

      <div className="mb-1">
        <span
          className="text-3xl font-bold tabular-nums"
          style={{ color: NAV_COLOR, fontFamily: "'Sora', sans-serif" }}
        >
          {isFree ? 'Free' : `$${Math.round(monthlyDisplayCents / 100)}`}
        </span>
        {!isFree && (
          <span className="text-sm ml-1" style={{ color: MUTED }}>
            /mo
          </span>
        )}
      </div>
      <div className="text-xs mb-5 min-h-[1rem]" style={{ color: MUTED }}>
        {!isFree && interval === 'yearly' && plan.price_yearly > 0
          ? `Billed annually at $${Math.round(plan.price_yearly / 100)}`
          : !isFree
            ? 'Billed monthly'
            : 'Forever'}
      </div>

      <button
        type="button"
        onClick={onSelect}
        disabled={isCurrent || loading || (!isFree && !canCheckout)}
        className="w-full py-2.5 rounded-md text-sm font-semibold transition mb-5 inline-flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
        style={{
          background: isPopular ? NAV_COLOR : 'white',
          color: isPopular ? 'white' : NAV_COLOR,
          border: `1px solid ${isPopular ? NAV_COLOR : BORDER}`,
        }}
      >
        {loading && <Loader2 size={14} className="animate-spin" />}
        {isCurrent
          ? 'Current plan'
          : isFree
            ? 'Get started'
            : !canCheckout
              ? 'Coming soon'
              : 'Choose plan'}
      </button>

      <ul className="space-y-2">
        {highlights.map((line) => (
          <li key={line} className="flex items-start gap-2">
            <Check
              size={14}
              className="mt-0.5 flex-shrink-0"
              style={{ color: ACCENT }}
            />
            <span className="text-xs leading-relaxed" style={{ color: NAV_COLOR }}>
              {line}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function EnterpriseCard({ onTalkToSales }: { onTalkToSales: () => void }) {
  return (
    <div
      className="rounded-2xl border p-8 mb-12"
      style={{
        background: 'linear-gradient(120deg, #0F1B2D 0%, #1A2D4A 100%)',
        borderColor: '#0F1B2D',
        color: 'white',
      }}
    >
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-6">
        <div className="max-w-xl">
          <p
            className="text-xs font-semibold tracking-[0.2em] uppercase mb-2"
            style={{ color: '#E5A840' }}
          >
            Enterprise
          </p>
          <h2
            className="text-2xl font-semibold mb-3"
            style={{ fontFamily: "'Sora', sans-serif" }}
          >
            A cheaper, sharper alternative to CoStar — for teams.
          </h2>
          <p className="text-sm leading-relaxed" style={{ color: 'rgba(255,255,255,0.7)' }}>
            SSO, shared workspaces, custom data sources, BYOK with your own
            LLM provider, and named onboarding. Most teams land between
            $200 – $400/seat — and replace 2-3 existing tools doing it.
          </p>
          <ul className="mt-4 grid sm:grid-cols-2 gap-x-6 gap-y-2 text-sm">
            {[
              'SSO & role-based access',
              'Shared workspaces and audit log',
              'BYOK at the workspace level',
              'Dedicated support & onboarding',
              'Custom data integrations',
              'Volume + multi-year discounts',
            ].map((line) => (
              <li key={line} className="flex items-start gap-2" style={{ color: 'rgba(255,255,255,0.85)' }}>
                <Check size={14} className="mt-0.5 flex-shrink-0" style={{ color: '#E5A840' }} />
                {line}
              </li>
            ))}
          </ul>
        </div>
        <button
          type="button"
          onClick={onTalkToSales}
          className="self-start md:self-center px-5 py-3 rounded-md font-semibold text-sm whitespace-nowrap"
          style={{ background: '#E5A840', color: NAV_COLOR }}
        >
          Talk to sales
        </button>
      </div>
    </div>
  );
}

function UsageSummary({
  subscription,
}: {
  subscription: SubscriptionWithUsage;
}) {
  const items: Array<{ label: string; used: number; limit: number }> = [
    {
      label: 'Chat sessions',
      used: subscription.usage.chat_session,
      limit: subscription.limits.chat_session,
    },
    {
      label: 'Tenant gap analyses',
      used: subscription.usage.void_analysis,
      limit: subscription.limits.void_analysis,
    },
    {
      label: 'Demographics',
      used: subscription.usage.demographics_report,
      limit: subscription.limits.demographics_report,
    },
    {
      label: 'Emails sent',
      used: subscription.usage.email_sent,
      limit: subscription.limits.email_sent,
    },
    {
      label: 'Documents',
      used: subscription.usage.document_parsed,
      limit: subscription.limits.document_parsed,
    },
  ];
  return (
    <div
      className="rounded-2xl border p-6 bg-white"
      style={{ borderColor: BORDER }}
    >
      <h2
        className="text-sm font-semibold uppercase tracking-wide mb-4"
        style={{ color: MUTED }}
      >
        Your usage this month
      </h2>
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        {items.map((item) => (
          <UsageCard key={item.label} {...item} />
        ))}
      </div>
    </div>
  );
}

function UsageCard({
  label,
  used,
  limit,
}: {
  label: string;
  used: number;
  limit: number;
}) {
  const unlimited = limit === -1;
  const pct = unlimited || limit === 0 ? 0 : (used / limit) * 100;
  const overCap = !unlimited && pct >= 100;
  return (
    <div
      className="rounded-xl border p-4"
      style={{ borderColor: BORDER, background: BG }}
    >
      <div
        className="text-[11px] font-semibold uppercase tracking-wide mb-1"
        style={{ color: MUTED }}
      >
        {label}
      </div>
      <div
        className="text-xl font-bold tabular-nums"
        style={{ color: NAV_COLOR, fontFamily: "'Sora', sans-serif" }}
      >
        {used} / {unlimited ? '∞' : limit}
      </div>
      {!unlimited && limit > 0 && (
        <div className="mt-2 h-1 rounded-full" style={{ background: BORDER }}>
          <div
            className="h-full rounded-full transition-all"
            style={{
              width: `${Math.min(pct, 100)}%`,
              background: overCap ? '#9B1C1C' : ACCENT,
            }}
          />
        </div>
      )}
    </div>
  );
}
