'use client';

import { useState, useCallback } from 'react';
import { useAuth } from '@/lib/auth-context';
import { api, adminApi } from '@/lib/api';

interface TestResult {
  name: string;
  status: 'pending' | 'running' | 'passed' | 'failed';
  message?: string;
  duration?: number;
}

interface TestGroup {
  name: string;
  tests: TestResult[];
}

export default function AdminTestsPage() {
  const { user } = useAuth();
  const [testGroups, setTestGroups] = useState<TestGroup[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [adminKey, setAdminKey] = useState('');
  const [createdAssistantId, setCreatedAssistantId] = useState<string | null>(null);

  const updateTest = useCallback((groupName: string, testName: string, update: Partial<TestResult>) => {
    setTestGroups(prev => prev.map(group => {
      if (group.name === groupName) {
        return {
          ...group,
          tests: group.tests.map(test =>
            test.name === testName ? { ...test, ...update } : test
          )
        };
      }
      return group;
    }));
  }, []);

  const runTest = useCallback(async (
    groupName: string,
    testName: string,
    testFn: () => Promise<void>
  ) => {
    const start = Date.now();
    updateTest(groupName, testName, { status: 'running' });

    try {
      await testFn();
      updateTest(groupName, testName, {
        status: 'passed',
        duration: Date.now() - start,
        message: 'Success'
      });
      return true;
    } catch (error) {
      updateTest(groupName, testName, {
        status: 'failed',
        duration: Date.now() - start,
        message: error instanceof Error ? error.message : 'Unknown error'
      });
      return false;
    }
  }, [updateTest]);

  const runAllTests = async () => {
    if (!user?.id) {
      alert('You must be logged in to run tests');
      return;
    }

    setIsRunning(true);
    setCreatedAssistantId(null);

    // Initialize test groups
    const initialGroups: TestGroup[] = [
      {
        name: 'Health & Connection',
        tests: [
          { name: 'API Health Check', status: 'pending' },
        ]
      },
      {
        name: 'User Data',
        tests: [
          { name: 'Get Subscription', status: 'pending' },
          { name: 'Get Usage', status: 'pending' },
          { name: 'Get Feature Limits', status: 'pending' },
        ]
      },
      {
        name: 'Assistants CRUD',
        tests: [
          { name: 'List Assistants', status: 'pending' },
          { name: 'Create Assistant', status: 'pending' },
          { name: 'Get Assistant', status: 'pending' },
          { name: 'Update Assistant', status: 'pending' },
          { name: 'Delete Assistant', status: 'pending' },
        ]
      },
      {
        name: 'Call Logs',
        tests: [
          { name: 'Get Call Stats', status: 'pending' },
          { name: 'List Calls', status: 'pending' },
        ]
      },
      {
        name: 'Payments',
        tests: [
          { name: 'Create Checkout Session', status: 'pending' },
          { name: 'Create Portal Session', status: 'pending' },
        ]
      },
    ];

    // Add admin tests if key provided
    if (adminKey) {
      initialGroups.push({
        name: 'Admin Functions',
        tests: [
          { name: 'Get User Subscription', status: 'pending' },
          { name: 'List Discount Codes', status: 'pending' },
        ]
      });
    }

    setTestGroups(initialGroups);

    // Run Health tests
    await runTest('Health & Connection', 'API Health Check', async () => {
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || 'https://web-production-1b085.up.railway.app'}/health`
      );
      if (!response.ok) throw new Error(`Status: ${response.status}`);
      const data = await response.json();
      if (data.status !== 'healthy') throw new Error('API unhealthy');
    });

    // Run User Data tests
    await runTest('User Data', 'Get Subscription', async () => {
      const result = await api.getSubscription(user.id);
      if (!('subscription' in result)) throw new Error('Invalid response');
    });

    await runTest('User Data', 'Get Usage', async () => {
      const result = await api.getUsage(user.id);
      if (!result.usage) throw new Error('No usage data');
      if (typeof result.usage.minutes_used !== 'number') throw new Error('Invalid minutes');
    });

    await runTest('User Data', 'Get Feature Limits', async () => {
      const result = await api.getFeatureLimits(user.id);
      if (!result.limits) throw new Error('No limits data');
      if (typeof result.limits.max_minutes !== 'number') throw new Error('Invalid limits');
    });

    // Run Assistants tests
    await runTest('Assistants CRUD', 'List Assistants', async () => {
      const result = await api.getAssistants(user.id);
      if (!Array.isArray(result.assistants)) throw new Error('Invalid response');
    });

    let testAssistantId: string | null = null;

    const createSuccess = await runTest('Assistants CRUD', 'Create Assistant', async () => {
      const result = await api.createAssistant(user.id, {
        name: `Test Assistant ${Date.now()}`,
        system_prompt: 'You are a test assistant for API testing.',
        description: 'Created by admin test dashboard',
        voice_id: 'default',
        model: 'claude-sonnet-4-5-20250929',
        temperature: 0.7,
        max_tokens: 150,
      });
      if (!result.success || !result.assistant?.id) throw new Error('Failed to create');
      testAssistantId = result.assistant.id;
      setCreatedAssistantId(result.assistant.id);
    });

    if (createSuccess && testAssistantId) {
      await runTest('Assistants CRUD', 'Get Assistant', async () => {
        const result = await api.getAssistant(user.id, testAssistantId!);
        if (!result.assistant?.id) throw new Error('Not found');
      });

      await runTest('Assistants CRUD', 'Update Assistant', async () => {
        const result = await api.updateAssistant(user.id, testAssistantId!, {
          name: `Updated Test ${Date.now()}`,
          is_active: false,
        });
        if (!result.success) throw new Error('Update failed');
      });

      await runTest('Assistants CRUD', 'Delete Assistant', async () => {
        const result = await api.deleteAssistant(user.id, testAssistantId!);
        if (!result.success) throw new Error('Delete failed');
        setCreatedAssistantId(null);
      });
    } else {
      // Mark dependent tests as failed
      updateTest('Assistants CRUD', 'Get Assistant', {
        status: 'failed',
        message: 'Skipped - Create failed'
      });
      updateTest('Assistants CRUD', 'Update Assistant', {
        status: 'failed',
        message: 'Skipped - Create failed'
      });
      updateTest('Assistants CRUD', 'Delete Assistant', {
        status: 'failed',
        message: 'Skipped - Create failed'
      });
    }

    // Run Call Logs tests
    await runTest('Call Logs', 'Get Call Stats', async () => {
      const result = await api.getCallStats(user.id);
      if (!result.stats) throw new Error('No stats');
      if (typeof result.stats.total_calls !== 'number') throw new Error('Invalid stats');
    });

    await runTest('Call Logs', 'List Calls', async () => {
      const result = await api.getCalls(user.id, 10, 0);
      if (!Array.isArray(result.calls)) throw new Error('Invalid response');
      if (typeof result.total !== 'number') throw new Error('Missing total');
    });

    // Run Payments tests
    await runTest('Payments', 'Create Checkout Session', async () => {
      try {
        const result = await api.createCheckoutSession(
          user.id,
          'starter',
          window.location.href,
          window.location.href
        );
        if (!result.url) throw new Error('No checkout URL');
      } catch (error) {
        // Stripe might not be configured - check for specific error
        const msg = error instanceof Error ? error.message : '';
        if (msg.includes('Stripe') || msg.includes('stripe') || msg.includes('API key')) {
          throw new Error('Stripe not configured (expected in dev)');
        }
        throw error;
      }
    });

    await runTest('Payments', 'Create Portal Session', async () => {
      try {
        const result = await api.createPortalSession(user.id, window.location.href);
        if (!result.url) throw new Error('No portal URL');
      } catch (error) {
        const msg = error instanceof Error ? error.message : '';
        if (msg.includes('Stripe') || msg.includes('stripe') || msg.includes('API key') || msg.includes('customer')) {
          throw new Error('No Stripe customer (expected in dev)');
        }
        throw error;
      }
    });

    // Run Admin tests if key provided
    if (adminKey) {
      await runTest('Admin Functions', 'Get User Subscription', async () => {
        const result = await adminApi.getUserSubscription(adminKey, user.id);
        if (!('user_id' in result)) throw new Error('Invalid response');
      });

      await runTest('Admin Functions', 'List Discount Codes', async () => {
        const result = await adminApi.getCodes(adminKey);
        if (!Array.isArray(result.codes)) throw new Error('Invalid response');
      });
    }

    setIsRunning(false);
  };

  const getStatusIcon = (status: TestResult['status']) => {
    switch (status) {
      case 'passed':
        return <span className="text-green-400">&#10003;</span>;
      case 'failed':
        return <span className="text-red-400">&#10007;</span>;
      case 'running':
        return <span className="text-yellow-400 animate-spin">&#8635;</span>;
      default:
        return <span className="text-gray-500">&#9679;</span>;
    }
  };

  const getTotalStats = () => {
    let passed = 0, failed = 0, total = 0;
    testGroups.forEach(group => {
      group.tests.forEach(test => {
        total++;
        if (test.status === 'passed') passed++;
        if (test.status === 'failed') failed++;
      });
    });
    return { passed, failed, total };
  };

  const stats = getTotalStats();

  return (
    <div className="max-w-4xl mx-auto">
      <h1 className="text-3xl font-bold text-gold mb-2">API Test Dashboard</h1>
      <p className="text-gray-400 mb-6">Test all API endpoints and verify functionality</p>

      {/* Admin Key Input */}
      <div className="bg-oled-dark border border-gold/20 rounded-lg p-4 mb-6">
        <label className="block text-sm text-gray-400 mb-2">
          Admin Key (optional - enables admin endpoint tests)
        </label>
        <input
          type="password"
          value={adminKey}
          onChange={(e) => setAdminKey(e.target.value)}
          placeholder="Enter admin key..."
          className="w-full px-3 py-2 bg-black border border-gray-700 rounded text-white
            placeholder-gray-500 focus:border-gold focus:outline-none"
        />
      </div>

      {/* Run Button */}
      <div className="flex items-center gap-4 mb-6">
        <button
          onClick={runAllTests}
          disabled={isRunning || !user}
          className={`px-6 py-3 rounded-lg font-medium transition-all ${
            isRunning || !user
              ? 'bg-gray-700 text-gray-400 cursor-not-allowed'
              : 'bg-gold text-black hover:bg-gold/80'
          }`}
        >
          {isRunning ? 'Running Tests...' : 'Run All Tests'}
        </button>

        {testGroups.length > 0 && (
          <div className="flex gap-4 text-sm">
            <span className="text-green-400">{stats.passed} passed</span>
            <span className="text-red-400">{stats.failed} failed</span>
            <span className="text-gray-400">{stats.total} total</span>
          </div>
        )}
      </div>

      {/* Test Results */}
      {testGroups.length > 0 && (
        <div className="space-y-4">
          {testGroups.map((group) => (
            <div key={group.name} className="bg-oled-dark border border-gold/20 rounded-lg overflow-hidden">
              <div className="px-4 py-3 border-b border-gold/10">
                <h3 className="text-lg font-semibold text-gold">{group.name}</h3>
              </div>
              <div className="divide-y divide-gray-800">
                {group.tests.map((test) => (
                  <div key={test.name} className="px-4 py-3 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <span className="text-lg">{getStatusIcon(test.status)}</span>
                      <span className="text-white">{test.name}</span>
                    </div>
                    <div className="flex items-center gap-3 text-sm">
                      {test.duration && (
                        <span className="text-gray-500">{test.duration}ms</span>
                      )}
                      {test.message && test.status === 'failed' && (
                        <span className="text-red-400 max-w-xs truncate">{test.message}</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* WebSocket Test Note */}
      <div className="mt-6 p-4 bg-blue-500/10 border border-blue-500/30 rounded-lg">
        <h4 className="text-blue-400 font-medium mb-2">WebSocket Voice Test</h4>
        <p className="text-gray-400 text-sm">
          To test WebSocket voice streaming, go to the{' '}
          <a href="/dashboard/assistants" className="text-gold hover:underline">
            Assistants page
          </a>{' '}
          and click &quot;Start Call&quot; on any active assistant.
        </p>
      </div>

      {/* Empty State */}
      {testGroups.length === 0 && (
        <div className="text-center py-12 text-gray-500">
          <p className="text-lg mb-2">No test results yet</p>
          <p className="text-sm">Click &quot;Run All Tests&quot; to test API endpoints</p>
        </div>
      )}
    </div>
  );
}
