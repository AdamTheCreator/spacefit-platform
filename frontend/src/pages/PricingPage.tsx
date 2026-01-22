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
      <div className="min-h-screen bg-gray-900 flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
      </div>
    );
  }

  const currentTier = currentSubscription?.subscription.tier || 'free';

  return (
    <div className="min-h-screen bg-gray-900 py-12 px-4">
      <div className="max-w-6xl mx-auto">
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold text-white mb-4">
            Simple, transparent pricing
          </h1>
          <p className="text-xl text-gray-400">
            Choose the plan that fits your commercial real estate business
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-8">
          {plans.map((plan) => {
            const isCurrentPlan = currentTier === plan.tier;
            const isPopular = plan.tier === 'pro';

            return (
              <div
                key={plan.id}
                className={`relative bg-gray-800/50 border rounded-xl p-8 ${
                  isPopular
                    ? 'border-blue-500 ring-2 ring-blue-500/20'
                    : 'border-gray-700'
                }`}
              >
                {isPopular && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                    <span className="bg-blue-500 text-white text-sm font-medium px-3 py-1 rounded-full">
                      Most Popular
                    </span>
                  </div>
                )}

                <div className="mb-6">
                  <h2 className="text-2xl font-bold text-white mb-2">{plan.name}</h2>
                  <p className="text-gray-400 text-sm h-12">{plan.description}</p>
                </div>

                <div className="mb-6">
                  <span className="text-4xl font-bold text-white">
                    {formatPrice(plan.price_monthly)}
                  </span>
                  {plan.price_monthly > 0 && (
                    <span className="text-gray-400">/month</span>
                  )}
                </div>

                <button
                  onClick={() => handleSelectPlan(plan.tier)}
                  disabled={isCurrentPlan || checkoutLoading === plan.tier}
                  className={`w-full py-3 px-4 rounded-lg font-medium transition mb-8 ${
                    isCurrentPlan
                      ? 'bg-gray-700 text-gray-400 cursor-not-allowed'
                      : isPopular
                      ? 'bg-blue-500 hover:bg-blue-600 text-white'
                      : 'bg-gray-700 hover:bg-gray-600 text-white'
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
                  <h3 className="text-sm font-medium text-gray-300 uppercase tracking-wider">
                    What's included
                  </h3>

                  <FeatureItem
                    included
                    label={`${formatLimit(plan.chat_sessions_per_month)} AI chat sessions/mo`}
                  />
                  <FeatureItem
                    included
                    label={`${formatLimit(plan.void_analyses_per_month)} void analyses/mo`}
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

                  <div className="pt-4 border-t border-gray-700">
                    <h3 className="text-sm font-medium text-gray-300 uppercase tracking-wider mb-4">
                      Data Sources
                    </h3>
                    <FeatureItem included label="Census Bureau" />
                    <FeatureItem included={plan.has_placer_access} label="Placer.ai" />
                    <FeatureItem included={plan.has_siteusa_access} label="SiteUSA" />
                    <FeatureItem included={plan.has_costar_access} label="CoStar" />
                  </div>

                  <div className="pt-4 border-t border-gray-700">
                    <h3 className="text-sm font-medium text-gray-300 uppercase tracking-wider mb-4">
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
          <div className="mt-12 bg-gray-800/50 border border-gray-700 rounded-xl p-6">
            <h2 className="text-xl font-bold text-white mb-4">Your Usage This Month</h2>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
              <UsageItem
                label="Chat Sessions"
                used={currentSubscription.usage.chat_session}
                limit={currentSubscription.limits.chat_session}
              />
              <UsageItem
                label="Void Analyses"
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

        <div className="mt-12 text-center text-gray-400">
          <p>Need a custom plan for your team?</p>
          <a href="mailto:sales@spacefit.ai" className="text-blue-400 hover:text-blue-300">
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
        <Check className="h-5 w-5 text-green-400 flex-shrink-0" />
      ) : (
        <X className="h-5 w-5 text-gray-600 flex-shrink-0" />
      )}
      <span className={included ? 'text-gray-300' : 'text-gray-500'}>{label}</span>
    </div>
  );
}

function UsageItem({ label, used, limit }: { label: string; used: number; limit: number }) {
  const isUnlimited = limit === -1;
  const percentage = isUnlimited ? 0 : limit > 0 ? (used / limit) * 100 : 0;
  const isNearLimit = !isUnlimited && percentage >= 80;
  const isAtLimit = !isUnlimited && percentage >= 100;

  return (
    <div className="bg-gray-800 rounded-lg p-4">
      <div className="text-sm text-gray-400 mb-1">{label}</div>
      <div className="text-xl font-bold text-white">
        {used} / {isUnlimited ? '∞' : limit}
      </div>
      {!isUnlimited && limit > 0 && (
        <div className="mt-2 h-2 bg-gray-700 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all ${
              isAtLimit ? 'bg-red-500' : isNearLimit ? 'bg-yellow-500' : 'bg-blue-500'
            }`}
            style={{ width: `${Math.min(percentage, 100)}%` }}
          />
        </div>
      )}
    </div>
  );
}
