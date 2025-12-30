'use client';

import { useState, useEffect } from 'react';
import { Card, CardTitle, CardContent } from '@/components/Card';
import { HoneycombButton } from '@/components/HoneycombButton';
import { useAuth } from '@/lib/auth-context';
import { profileApi } from '@/lib/api';

interface ProfileField {
  label: string;
  value: string;
}

export default function ProfilePage() {
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [plan, setPlan] = useState('free');
  const [fieldLimits, setFieldLimits] = useState({ max_fields: 1, max_chars_per_field: 60 });

  const [profile, setProfile] = useState({
    display_name: '',
    business_name: '',
    profession: '',
    service_area: '',
    greeting_name: '',
    assistant_name: 'Assistant',
    assistant_personality: '',
    timezone: 'America/New_York',
  });

  const [profileFields, setProfileFields] = useState<ProfileField[]>([]);

  useEffect(() => {
    const fetchProfile = async () => {
      if (!user?.id) return;
      try {
        const response = await profileApi.getExtendedProfile(user.id);
        setProfile(prev => ({ ...prev, ...response.profile }));
        setFieldLimits(response.field_limits);
        setPlan(response.plan);
        if (response.profile.profile_fields) {
          setProfileFields(response.profile.profile_fields);
        }
      } catch (error) {
        console.error('Failed to load profile:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchProfile();
  }, [user?.id]);

  const addField = () => {
    if (profileFields.length < fieldLimits.max_fields) {
      setProfileFields([...profileFields, { label: '', value: '' }]);
    }
  };

  const updateField = (index: number, key: 'label' | 'value', value: string) => {
    const truncatedValue = value.slice(0, fieldLimits.max_chars_per_field);
    const newFields = [...profileFields];
    newFields[index][key] = truncatedValue;
    setProfileFields(newFields);
    setSaved(false);
  };

  const removeField = (index: number) => {
    setProfileFields(profileFields.filter((_, i) => i !== index));
    setSaved(false);
  };

  const saveProfile = async () => {
    if (!user?.id) return;
    setSaving(true);
    try {
      await profileApi.updateProfile(user.id, {
        ...profile,
        profile_fields: profileFields,
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (error) {
      console.error('Failed to save profile:', error);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gold text-xl">Loading profile...</div>
      </div>
    );
  }

  const planColors: Record<string, string> = {
    free: 'bg-gray-600',
    starter: 'bg-blue-600',
    pro: 'bg-gold',
    enterprise: 'bg-purple-600',
  };

  return (
    <div className="space-y-6 max-w-3xl">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gold">Profile</h1>
          <p className="text-gray-400 mt-1">Your business info for AI assistant</p>
        </div>
        <div className="flex items-center gap-4">
          <span className={`px-3 py-1 rounded-full text-sm text-white ${planColors[plan]}`}>
            {plan.charAt(0).toUpperCase() + plan.slice(1)} Plan
          </span>
          <HoneycombButton onClick={saveProfile} disabled={saving}>
            {saving ? 'Saving...' : saved ? 'Saved!' : 'Save Profile'}
          </HoneycombButton>
        </div>
      </div>

      {/* Basic Info */}
      <Card>
        <CardTitle>Basic Information</CardTitle>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
            <div>
              <label className="block text-sm text-gray-400 mb-2">Display Name</label>
              <input
                type="text"
                value={profile.display_name}
                onChange={(e) => setProfile({ ...profile, display_name: e.target.value })}
                placeholder="John Smith"
                className="w-full bg-oled-gray border border-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:border-gold focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-2">Business Name</label>
              <input
                type="text"
                value={profile.business_name}
                onChange={(e) => setProfile({ ...profile, business_name: e.target.value })}
                placeholder="Smith Electric LLC"
                className="w-full bg-oled-gray border border-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:border-gold focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-2">Profession</label>
              <input
                type="text"
                value={profile.profession}
                onChange={(e) => setProfile({ ...profile, profession: e.target.value })}
                placeholder="Licensed Electrician"
                className="w-full bg-oled-gray border border-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:border-gold focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-2">Service Area</label>
              <input
                type="text"
                value={profile.service_area}
                onChange={(e) => setProfile({ ...profile, service_area: e.target.value })}
                placeholder="Philadelphia Metro Area"
                className="w-full bg-oled-gray border border-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:border-gold focus:outline-none"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* AI Assistant Settings */}
      <Card>
        <CardTitle>AI Assistant</CardTitle>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
            <div>
              <label className="block text-sm text-gray-400 mb-2">Greeting Name</label>
              <input
                type="text"
                value={profile.greeting_name}
                onChange={(e) => setProfile({ ...profile, greeting_name: e.target.value })}
                placeholder="How AI addresses you"
                className="w-full bg-oled-gray border border-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:border-gold focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-2">Assistant Name</label>
              <input
                type="text"
                value={profile.assistant_name}
                onChange={(e) => setProfile({ ...profile, assistant_name: e.target.value })}
                placeholder="Assistant"
                className="w-full bg-oled-gray border border-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:border-gold focus:outline-none"
              />
            </div>
            <div className="md:col-span-2">
              <label className="block text-sm text-gray-400 mb-2">Assistant Personality</label>
              <textarea
                value={profile.assistant_personality}
                onChange={(e) => setProfile({ ...profile, assistant_personality: e.target.value })}
                placeholder="Describe how your AI should behave (e.g., Professional and friendly, always asks for callback number)"
                rows={3}
                className="w-full bg-oled-gray border border-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:border-gold focus:outline-none resize-none"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Profile Fields (Tier Limited) */}
      <Card glow>
        <CardTitle>
          <div className="flex justify-between items-center">
            <span>Business Details</span>
            <span className="text-sm font-normal text-gray-400">
              {profileFields.length} / {fieldLimits.max_fields} fields ({fieldLimits.max_chars_per_field} chars each)
            </span>
          </div>
        </CardTitle>
        <CardContent>
          <p className="text-gray-400 text-sm mb-4">
            These fields are shared with the AI to help answer calls. The AI will use this info to respond to callers.
          </p>

          <div className="space-y-4 mt-4">
            {profileFields.map((field, index) => (
              <div key={index} className="flex gap-3 items-start">
                <div className="flex-1">
                  <input
                    type="text"
                    value={field.label}
                    onChange={(e) => updateField(index, 'label', e.target.value)}
                    placeholder="Field label (e.g., Services)"
                    className="w-full bg-oled-gray border border-gray-700 rounded-lg px-4 py-2 text-white text-sm placeholder-gray-500 focus:border-gold focus:outline-none mb-2"
                  />
                  <textarea
                    value={field.value}
                    onChange={(e) => updateField(index, 'value', e.target.value)}
                    placeholder="Field value (e.g., Panel upgrades, rewiring, EV chargers)"
                    rows={2}
                    className="w-full bg-oled-gray border border-gray-700 rounded-lg px-4 py-2 text-white text-sm placeholder-gray-500 focus:border-gold focus:outline-none resize-none"
                  />
                  <div className="text-xs text-gray-500 mt-1 text-right">
                    {field.value.length} / {fieldLimits.max_chars_per_field}
                  </div>
                </div>
                <button
                  onClick={() => removeField(index)}
                  className="p-2 text-gray-500 hover:text-red-500 transition-colors"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            ))}

            {profileFields.length < fieldLimits.max_fields ? (
              <button
                onClick={addField}
                className="w-full py-3 border-2 border-dashed border-gray-700 rounded-lg text-gray-400 hover:border-gold hover:text-gold transition-colors"
              >
                + Add Field
              </button>
            ) : (
              <div className="text-center py-3 text-gray-500">
                {plan === 'free' || plan === 'starter' ? (
                  <span>
                    Upgrade to add more fields. <a href="/dashboard/subscription" className="text-gold hover:underline">View plans</a>
                  </span>
                ) : (
                  <span>Maximum fields reached for your plan</span>
                )}
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Preview */}
      <Card>
        <CardTitle>AI Knowledge Preview</CardTitle>
        <CardContent>
          <div className="mt-4 p-4 bg-oled-gray rounded-lg text-sm text-gray-300 font-mono">
            <p className="text-gold mb-2">// What the AI knows about you:</p>
            <p>Business: {profile.business_name || 'Not set'}</p>
            <p>Profession: {profile.profession || 'Not set'}</p>
            <p>Service Area: {profile.service_area || 'Not set'}</p>
            {profileFields.length > 0 && (
              <>
                <p className="mt-2 text-gold">// Custom fields:</p>
                {profileFields.map((field, i) => (
                  <p key={i}>{field.label}: {field.value}</p>
                ))}
              </>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
