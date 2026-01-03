'use client';

import { useState, useEffect } from 'react';
import { Card, CardTitle, CardContent } from '@/components/Card';
import { HoneycombButton } from '@/components/HoneycombButton';
import { useAuth } from '@/lib/auth-context';
import { api } from '@/lib/api';

const plans = [
  {
    name: 'worker_bee',
    display: 'The Worker Bee',
    price: 97,
    minutes: 400,
    assistants: -1,
    voiceClones: 1,
    platforms: 'All platforms',
    analytics: 'Basic logs',
    callSharing: true,
    teamMembers: 1,
    webhooks: false,
    crmIntegrations: false,
    support: 'Email',
    phoneNumbers: 1,
  },
  {
    name: 'swarm',
    display: 'The Swarm',
    price: 297,
    minutes: 1350,
    assistants: -1,
    voiceClones: 3,
    platforms: 'All platforms',
    analytics: 'Full analytics',
    callSharing: true,
    teamMembers: 3,
    webhooks: true,
    crmIntegrations: false,
    support: 'Priority Email',
    phoneNumbers: 3,
    popular: true,
  },
  {
    name: 'queen_bee',
    display: 'The Queen Bee',
    price: 697,
    minutes: 3500,
    assistants: -1,
    voiceClones: 10,
    platforms: 'All platforms',
    analytics: 'Advanced analytics',
    callSharing: true,
    teamMembers: 10,
    webhooks: true,
    crmIntegrations: true,
    support: 'Live Chat',
    phoneNumbers: 10,
  },
  {
    name: 'hive_mind',
    display: 'The Hive Mind',
    price: null,
    minutes: 10000,
    assistants: -1,
    voiceClones: -1,
    platforms: 'All platforms + White Label',
    analytics: 'Custom dashboards',
    callSharing: true,
    teamMembers: -1,
    webhooks: true,
    crmIntegrations: true,
    support: 'Dedicated Rep',
    phoneNumbers: -1,
    enterprise: true,
  },
];

export default function SubscriptionPage() {
  const { user } = useAuth();
  const [currentPlan, setCurrentPlan] = useState<string | null>(null);
  const [loading, setLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isTrial, setIsTrial] = useState(false);
  const [trialEnd, setTrialEnd] = useState<string | null>(null);
  const [trialLoading, setTrialLoading] = useState(false);

  useEffect(() => {
    const fetchSubscription = async () => {
      if (!user?.id) return;
      try {
        const response = await api.getSubscription(user.id);
        if (response.subscription?.plan_name) {
          setCurrentPlan(response.subscription.plan_name);
          setIsTrial(response.subscription.is_trial || false);
          setTrialEnd(response.subscription.trial_end || null);
        }
      } catch (err) {
        console.error('Failed to fetch subscription:', err);
      }
    };
    fetchSubscription();
  }, [user?.id]);

  const handleStartTrial = async () => {
    if (!user?.id) return;
    setTrialLoading(true);
    setError(null);
    try {
      const response = await api.startTrial(user.id);
      if (response.success) {
        setCurrentPlan('swarm');
        setIsTrial(true);
        setTrialEnd(response.trial_end);
        alert('30-day trial started! Enjoy The Swarm features.');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start trial');
    } finally {
      setTrialLoading(false);
    }
  };

  const handleUpgrade = async (planName: string) => {
    if (!user?.id) return;

    setLoading(planName);
    setError(null);

    try {
      const response = await api.createCheckoutSession(
        user.id,
        planName,
        `${window.location.origin}/dashboard/subscription?success=true`,
        `${window.location.origin}/dashboard/subscription?canceled=true`
      );

      if (response.url) {
        window.location.href = response.url;
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create checkout session');
      setLoading(null);
    }
  };

  const handleManageBilling = async () => {
    if (!user?.id) return;

    setError(null);

    try {
      const response = await api.createPortalSession(
        user.id,
        `${window.location.origin}/dashboard/subscription`
      );

      if (response.url) {
        window.location.href = response.url;
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to open billing portal');
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-gold">Subscription</h1>
        <p className="text-gray-400 mt-1">Manage your plan and billing</p>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 text-red-400">
          {error}
        </div>
      )}

      {/* Current Plan Summary */}
      <Card glow>
        <CardContent>
          <div className="flex justify-between items-center">
            <div>
              <div className="text-sm text-gray-400">Current Plan</div>
              <div className="text-2xl font-bold text-gold">
                {plans.find(p => p.name === currentPlan)?.display}
                {isTrial && <span className="ml-2 text-sm font-normal text-yellow-400">(Trial)</span>}
              </div>
              <div className="text-gray-300">
                {isTrial && trialEnd ? (
                  <span>Trial ends {new Date(trialEnd).toLocaleDateString()}</span>
                ) : (
                  <span>${plans.find(p => p.name === currentPlan)?.price}/month</span>
                )}
              </div>
            </div>
            <HoneycombButton variant="outline" onClick={handleManageBilling}>
              Manage Billing
            </HoneycombButton>
          </div>
        </CardContent>
      </Card>

      {/* Trial Banner - Show for new users */}
      {!currentPlan && !isTrial && (
        <Card className="border-yellow-500/30 bg-gradient-to-r from-yellow-500/10 to-gold/10">
          <CardContent>
            <div className="flex justify-between items-center">
              <div>
                <div className="text-xl font-bold text-yellow-400">🐝 Try The Swarm Free for 14 Days!</div>
                <p className="text-gray-300 mt-1">
                  Start with our most popular plan: 1,350 minutes, 3 voice clones, webhooks, and priority support.
                </p>
                <p className="text-sm text-gray-400 mt-2">
                  No credit card required. Cancel anytime.
                </p>
              </div>
              <HoneycombButton onClick={handleStartTrial} disabled={trialLoading}>
                {trialLoading ? 'Starting...' : 'Start Free Trial'}
              </HoneycombButton>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Plan Comparison */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {plans.map((plan) => (
          <Card
            key={plan.name}
            glow={plan.popular}
            className={plan.name === currentPlan ? 'ring-2 ring-gold' : ''}
          >
            <CardContent>
              {plan.popular && (
                <div className="text-xs text-gold font-semibold mb-2">
                  MOST POPULAR
                </div>
              )}

              <div className="text-xl font-bold text-gold">{plan.display}</div>

              <div className="mt-2">
                {plan.price !== null ? (
                  <span className="text-3xl font-bold text-white">${plan.price}</span>
                ) : (
                  <span className="text-xl font-bold text-white">Custom</span>
                )}
                {plan.price !== null && (
                  <span className="text-gray-400 text-sm">/mo</span>
                )}
              </div>

              <div className="mt-4 space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-400">Minutes/month</span>
                  <span className="text-white">
                    {plan.minutes === -1 ? 'Unlimited' : plan.minutes.toLocaleString()}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Assistants</span>
                  <span className="text-white">
                    {plan.assistants === -1 ? 'Unlimited' : plan.assistants}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Voice Clones</span>
                  <span className="text-white">
                    {plan.voiceClones === -1 ? 'Unlimited' : plan.voiceClones}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Platforms</span>
                  <span className="text-white">{plan.platforms}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Phone Numbers</span>
                  <span className="text-white">
                    {(plan as { phoneNumbers?: number }).phoneNumbers === -1 ? 'Unlimited' : (plan as { phoneNumbers?: number }).phoneNumbers}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Team Members</span>
                  <span className="text-white">
                    {plan.teamMembers === -1 ? 'Unlimited' : plan.teamMembers}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Webhooks</span>
                  <span className={plan.webhooks ? 'text-green-500' : 'text-gray-500'}>
                    {plan.webhooks ? '✓' : '—'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">CRM Integrations</span>
                  <span className={plan.crmIntegrations ? 'text-green-500' : 'text-gray-500'}>
                    {plan.crmIntegrations ? '✓' : '—'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Analytics</span>
                  <span className="text-white">{plan.analytics}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Support</span>
                  <span className="text-white">{plan.support}</span>
                </div>
              </div>

              <div className="mt-6">
                {plan.name === currentPlan ? (
                  <div className="text-center py-2 text-gold font-semibold">
                    Current Plan
                  </div>
                ) : plan.name === 'hive_mind' ? (
                  <HoneycombButton
                    className="w-full"
                    variant="outline"
                    onClick={() => window.location.href = 'mailto:sales@hive215.com?subject=The%20Hive%20Mind%20Enterprise%20Inquiry'}
                  >
                    Contact Sales
                  </HoneycombButton>
                ) : (
                  <HoneycombButton
                    className="w-full"
                    onClick={() => handleUpgrade(plan.name)}
                    disabled={loading === plan.name}
                  >
                    {loading === plan.name ? 'Loading...' : 'Upgrade'}
                  </HoneycombButton>
                )}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* FAQ */}
      <Card>
        <CardTitle>Frequently Asked Questions</CardTitle>
        <CardContent>
          <div className="mt-4 space-y-4">
            <div>
              <div className="font-semibold text-gold">Can I change plans anytime?</div>
              <div className="text-sm text-gray-400 mt-1">
                Yes! Upgrades take effect immediately. Downgrades apply at the end of your billing period.
              </div>
            </div>
            <div>
              <div className="font-semibold text-gold">What happens if I exceed my minutes?</div>
              <div className="text-sm text-gray-400 mt-1">
                You'll receive a warning at 80% usage. Once you reach 100%, voice calls will be paused until your next billing cycle or you upgrade.
              </div>
            </div>
            <div>
              <div className="font-semibold text-gold">Can I cancel anytime?</div>
              <div className="text-sm text-gray-400 mt-1">
                Yes, cancel anytime through the billing portal. You'll retain access until the end of your current billing period.
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
