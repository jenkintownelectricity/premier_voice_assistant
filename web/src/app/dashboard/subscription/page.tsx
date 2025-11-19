'use client';

import { useState, useEffect } from 'react';
import { Card, CardTitle, CardContent } from '@/components/Card';
import { HoneycombButton } from '@/components/HoneycombButton';
import { useAuth } from '@/lib/auth-context';
import { api } from '@/lib/api';

const plans = [
  {
    name: 'free',
    display: 'Free',
    price: 0,
    minutes: 100,
    assistants: 1,
    voiceClones: 0,
    customVoices: false,
    apiAccess: false,
    support: 'Community',
  },
  {
    name: 'starter',
    display: 'Starter',
    price: 99,
    minutes: 2000,
    assistants: 3,
    voiceClones: 2,
    customVoices: true,
    apiAccess: false,
    support: 'Email',
  },
  {
    name: 'pro',
    display: 'Pro',
    price: 299,
    minutes: 10000,
    assistants: -1,
    voiceClones: -1,
    customVoices: true,
    apiAccess: true,
    support: 'Priority',
    popular: true,
  },
  {
    name: 'enterprise',
    display: 'Enterprise',
    price: null,
    minutes: -1,
    assistants: -1,
    voiceClones: -1,
    customVoices: true,
    apiAccess: true,
    support: 'Dedicated',
  },
];

export default function SubscriptionPage() {
  const { user } = useAuth();
  const [currentPlan, setCurrentPlan] = useState('free');
  const [loading, setLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchSubscription = async () => {
      if (!user?.id) return;
      try {
        const response = await api.getSubscription(user.id);
        if (response.subscription?.plan_name) {
          setCurrentPlan(response.subscription.plan_name);
        }
      } catch (err) {
        console.error('Failed to fetch subscription:', err);
      }
    };
    fetchSubscription();
  }, [user?.id]);

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
              </div>
              <div className="text-gray-300">
                ${plans.find(p => p.name === currentPlan)?.price}/month
              </div>
            </div>
            <HoneycombButton variant="outline" onClick={handleManageBilling}>
              Manage Billing
            </HoneycombButton>
          </div>
        </CardContent>
      </Card>

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
                  <span className="text-gray-400">Minutes</span>
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
                  <span className="text-gray-400">Custom Voices</span>
                  <span className={plan.customVoices ? 'text-green-500' : 'text-gray-500'}>
                    {plan.customVoices ? '✓' : '—'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">API Access</span>
                  <span className={plan.apiAccess ? 'text-green-500' : 'text-gray-500'}>
                    {plan.apiAccess ? '✓' : '—'}
                  </span>
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
                ) : plan.name === 'enterprise' ? (
                  <HoneycombButton
                    variant="outline"
                    className="w-full"
                    onClick={() => window.open('mailto:sales@premiervoice.ai')}
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
