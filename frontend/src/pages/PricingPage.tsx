import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Check, X, Loader2 } from 'lucide-react';
import api from '../lib/axios';
import type { Plan, SubscriptionWithUsage } from '../types/subscription';
import { useAuthStore } from '../stores/authStore';

export function PricingPage() {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuthStore();
  const [plans, setPlans] = useState<Plan[]>([]);
  const [currentSubscription, setCurrentSubscription] = useState<SubscriptionWithUsage | null>(null);
  const [loading, setLoading] = useState(true);
  const [checkoutLoading, setCheckoutLoading] = useState<string | null>(null);

  useEffect(() => {
    async function fetchData() {
      try {
        const plansResponse = await api.get<Plan[]>('/subscription/plans');
        setPlans(plansResponse.data);

        if (isAuthenticated) {
          const subResponse = await api.get<SubscriptionWithUsage>('/subscription/current');
          setCurrentSubscription(subResponse.data);
        }
      } catch (error) {
        console.error('Failed to fetch pricing data:', error);
      } finally {
        setLoading(false);
      }
    }

    fetchData();
  }, [isAuthenticated]);

  const handleSelectPlan = async (tier: string) => {
    if (!isAuthenticated) {
      navigate('/register', { state: { from: '/pricing', tier } });
      return;
    }

    if (tier === 'free') {
      return;
    }

    setCheckoutLoading(tier);
    try {
      const response = await api.post<{ checkout_url: string }>('/billing/checkout', {
        tier,
        success_url: `${window.location.origin}/settings?checkout=success`,
        cancel_url: `${window.location.origin}/pricing?checkout=canceled`,
      });
      window.location.href = response.data.checkout_url;
    } catch (error) {
      console.error('Failed to create checkout session:', error);
      setCheckoutLoading(null);
    }
  };

  const formatPrice = (cents: number) => {
    if (cents === 0) return 'Free';
    return `$${(cents / 100).toFixed(0)}`;
  };

  const formatLimit = (limit: number) => {
    if (limit === -1) return 'Unlimited';
    if (limit === 0) return '-';
    return limit.toString();
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: '#F8F8F7' }}>
        <div className="flex flex-col items-center gap-3">
          <Loader2 size={28} className="animate-spin" style={{ color: '#3A5BA0' }} />
          <p className="text-xs font-semibold tracking-widest uppercase" style={{ color: '#A3A19D' }}>Loading plans</p>
        </div>
      </div>
    );
  }

  const currentTier = currentSubscription?.subscription.tier || 'free';

  return (
    <div className="min-h-screen bg-industrial py-12 px-4 dark">
      <div className="max-w-6xl mx-auto">
        <div className="text-center mb-12">
          <h1 className="font-mono text-3xl font-bold tracking-tight text-industrial mb-4">
            Simple, transparent pricing
          </h1>
          <p className="font-mono text-sm text-industrial-secondary">
            Choose the plan that fits your commercial real estate business
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-8">
          {plans.map((plan) => {
            const isCurrentPlan = currentTier === plan.tier;
            const isPopular = plan.tier === 'individual';

            return (
              <div
                key={plan.id}
                className={`relative bg-[var(--bg-elevated)] border p-8 ${
                  isPopular
                    ? 'border-[var(--accent)] ring-1 ring-[var(--accent)]/20'
                    : 'border-industrial'
                }`}
              >
                {isPopular && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                    <span className="bg-[var(--accent)] text-[var(--color-industrial-900)] font-mono text-xs font-semibold uppercase tracking-wide px-3 py-1">
                      Most Popular
                    </span>
                  </div>
                )}

                <div className="mb-6">
                  <h2 className="font-mono text-xl font-bold tracking-tight text-industrial mb-2">{plan.name}</h2>
                  <p className="font-mono text-xs text-industrial-muted h-12">{plan.description}</p>
                </div>

                <div className="mb-6">
                  <span className="font-mono text-4xl font-bold text-[var(--accent)]">
                    {formatPrice(plan.price_monthly)}
                  </span>
                  {plan.price_monthly > 0 && (
                    <span className="font-mono text-sm text-industrial-muted">/month</span>
                  )}
                </div>

                <button
                  onClick={() => handleSelectPlan(plan.tier)}
                  disabled={isCurrentPlan || checkoutLoading === plan.tier}
                  className={`w-full py-3 px-4 font-mono text-xs uppercase tracking-wide font-semibold transition mb-8 ${
                    isCurrentPlan
                      ? 'bg-[var(--bg-tertiary)] text-industrial-muted cursor-not-allowed border border-industrial-subtle'
                      : isPopular
                      ? 'bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-[var(--color-industrial-900)] border border-[var(--accent)]'
                      : 'bg-[var(--bg-tertiary)] hover:bg-[var(--bg-secondary)] text-industrial border border-industrial-subtle'
                  }`}
                >
                  {checkoutLoading === plan.tier ? (
                    <Loader2 className="h-5 w-5 animate-spin mx-auto" />
                  ) : isCurrentPlan ? (
                    'Current Plan'
                  ) : plan.tier === 'free' ? (
                    'Get Started'
                  ) : (
                    'Upgrade'
                  )}
                </button>

                <div className="space-y-4">
                  <h3 className="label-technical">
                    What's included
                  </h3>

                  <FeatureItem
                    included
                    label={`${formatLimit(plan.chat_sessions_per_month)} AI chat sessions/mo`}
                  />
                  <FeatureItem
                    included
                    label={`${formatLimit(plan.void_analyses_per_month)} tenant gap analyses/mo`}
                  />
                  <FeatureItem
                    included
                    label={`${formatLimit(plan.demographics_reports_per_month)} demographics reports/mo`}
                  />
                  <FeatureItem
                    included={plan.emails_per_month > 0}
                    label={
                      plan.emails_per_month > 0
                        ? `${formatLimit(plan.emails_per_month)} emails/mo`
                        : 'Email outreach'
                    }
                  />
                  <FeatureItem
                    included
                    label={`${formatLimit(plan.documents_per_month)} documents/mo`}
                  />
                  <FeatureItem
                    included
                    label={`${formatLimit(plan.team_members)} team member${plan.team_members !== 1 ? 's' : ''}`}
                  />

                  <div className="pt-4 border-t border-industrial-subtle">
                    <h3 className="label-technical mb-4">
                      Data Sources
                    </h3>
                    <FeatureItem included label="Census Bureau" />
                    <FeatureItem included={plan.has_placer_access} label="Placer.ai" />
                    <FeatureItem included={plan.has_siteusa_access} label="SiteUSA" />
                    <FeatureItem included={plan.has_costar_access} label="CoStar" />
                  </div>

                  <div className="pt-4 border-t border-industrial-subtle">
                    <h3 className="label-technical mb-4">
                      Features
                    </h3>
                    <FeatureItem included={plan.has_email_outreach} label="Email Outreach" />
                    <FeatureItem included={plan.has_api_access} label="API Access" />
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {currentSubscription && (
          <div className="mt-12 bg-[var(--bg-elevated)] border border-industrial p-6">
            <h2 className="font-mono text-sm font-semibold uppercase tracking-wide text-industrial mb-4">Your Usage This Month</h2>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
              <UsageItem
                label="Chat Sessions"
                used={currentSubscription.usage.chat_session}
                limit={currentSubscription.limits.chat_session}
              />
              <UsageItem
                label="Tenant Gap Analyses"
                used={currentSubscription.usage.void_analysis}
                limit={currentSubscription.limits.void_analysis}
              />
              <UsageItem
                label="Demographics"
                used={currentSubscription.usage.demographics_report}
                limit={currentSubscription.limits.demographics_report}
              />
              <UsageItem
                label="Emails Sent"
                used={currentSubscription.usage.email_sent}
                limit={currentSubscription.limits.email_sent}
              />
              <UsageItem
                label="Documents"
                used={currentSubscription.usage.document_parsed}
                limit={currentSubscription.limits.document_parsed}
              />
            </div>
          </div>
        )}

        <div className="mt-12 text-center">
          <p className="font-mono text-xs text-industrial-muted">Need a custom plan for your team?</p>
          <a href="mailto:sales@perigee.ai" className="font-mono text-xs text-[var(--accent)] hover:underline uppercase tracking-wide">
            Contact us for Enterprise pricing
          </a>
        </div>
      </div>
    </div>
  );
}

function FeatureItem({ included, label }: { included: boolean; label: string }) {
  return (
    <div className="flex items-center gap-3">
      {included ? (
        <Check className="h-4 w-4 text-[var(--color-success)] flex-shrink-0" />
      ) : (
        <X className="h-4 w-4 text-industrial-muted flex-shrink-0" />
      )}
      <span className={`font-mono text-xs ${included ? 'text-industrial-secondary' : 'text-industrial-muted'}`}>{label}</span>
    </div>
  );
}

function UsageItem({ label, used, limit }: { label: string; used: number; limit: number }) {
  const isUnlimited = limit === -1;
  const percentage = isUnlimited ? 0 : limit > 0 ? (used / limit) * 100 : 0;
  const isNearLimit = !isUnlimited && percentage >= 80;
  const isAtLimit = !isUnlimited && percentage >= 100;

  return (
    <div className="bg-[var(--bg-tertiary)] border border-industrial-subtle p-4">
      <div className="label-technical mb-1">{label}</div>
      <div className="font-mono text-xl font-bold text-industrial">
        {used} / {isUnlimited ? '∞' : limit}
      </div>
      {!isUnlimited && limit > 0 && (
        <div className="mt-2 h-1 bg-[var(--bg-secondary)] overflow-hidden">
          <div
            className={`h-full transition-all ${
              isAtLimit ? 'bg-[var(--color-error)]' : isNearLimit ? 'bg-[var(--color-warning)]' : 'bg-[var(--accent)]'
            }`}
            style={{ width: `${Math.min(percentage, 100)}%` }}
          />
        </div>
      )}
    </div>
  );
}
