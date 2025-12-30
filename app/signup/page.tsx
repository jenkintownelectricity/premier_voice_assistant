'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/lib/auth-context';
import { Card, CardContent } from '@/components/Card';
import { HoneycombButton } from '@/components/HoneycombButton';
import { Input } from '@/components/Input';

export default function SignupPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const { signUp } = useAuth();
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    if (password.length < 6) {
      setError('Password must be at least 6 characters');
      return;
    }

    setLoading(true);

    try {
      const { error } = await signUp(email, password);
      if (error) {
        setError(error.message);
      } else {
        setSuccess(true);
      }
    } catch (err) {
      setError('An unexpected error occurred');
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <div className="min-h-screen bg-black flex items-center justify-center p-4">
        <div className="w-full max-w-md">
          <Card glow>
            <CardContent>
              <div className="text-center space-y-4">
                <div className="text-green-500 text-5xl">✓</div>
                <h2 className="text-2xl font-bold text-gold">Check your email</h2>
                <p className="text-gray-400">
                  We've sent a confirmation link to <span className="text-white">{email}</span>
                </p>
                <Link href="/login">
                  <HoneycombButton className="w-full mt-4">
                    Back to Login
                  </HoneycombButton>
                </Link>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-black flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo/Header */}
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-gold">HIVE215</h1>
          <p className="text-gray-400 mt-2">Create your account</p>
        </div>

        <Card glow>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              <Input
                label="Email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                required
              />

              <Input
                label="Password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
              />

              <Input
                label="Confirm Password"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="••••••••"
                required
              />

              {error && (
                <div className="text-red-400 text-sm bg-red-500/10 border border-red-500/30 rounded-lg p-3">
                  {error}
                </div>
              )}

              <HoneycombButton
                type="submit"
                className="w-full"
                disabled={loading}
              >
                {loading ? 'Creating account...' : 'Sign Up'}
              </HoneycombButton>
            </form>

            <div className="mt-6 text-center text-sm">
              <span className="text-gray-400">Already have an account? </span>
              <Link href="/login" className="text-gold hover:text-gold-shine">
                Sign in
              </Link>
            </div>
          </CardContent>
        </Card>

        {/* Terms */}
        <div className="mt-4 text-center text-xs text-gray-500">
          <p>By signing up, you agree to our Terms of Service and Privacy Policy</p>
        </div>
      </div>
    </div>
  );
}
