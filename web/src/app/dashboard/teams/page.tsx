'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardContent, CardTitle } from '@/components/Card';
import { useAuth } from '@/lib/auth-context';
import api from '@/lib/api';

interface Team {
  id: string;
  name: string;
  description?: string;
  owner_id: string;
  role: string;
  member_count: number;
  created_at: string;
}

interface TeamDetails {
  team: Team;
  members: Array<{
    id: string;
    user_id: string;
    role: string;
    joined_at: string;
  }>;
  user_role: string;
}

interface TeamAnalytics {
  team_totals: {
    total_cost_dollars: number;
    total_tokens: number;
    total_requests: number;
    total_errors: number;
    error_rate_percent: number;
  };
  by_member: Array<{
    user_id: string;
    cost_dollars: number;
    tokens: number;
    requests: number;
    errors: number;
  }>;
  member_count: number;
}

export default function TeamsPage() {
  const router = useRouter();
  const { user } = useAuth();
  const [teams, setTeams] = useState<Team[]>([]);
  const [selectedTeam, setSelectedTeam] = useState<string | null>(null);
  const [teamDetails, setTeamDetails] = useState<TeamDetails | null>(null);
  const [teamAnalytics, setTeamAnalytics] = useState<TeamAnalytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newTeamName, setNewTeamName] = useState('');
  const [newTeamDescription, setNewTeamDescription] = useState('');

  useEffect(() => {
    if (!user) {
      router.push('/login');
      return;
    }

    fetchTeams();
  }, [user, router]);

  useEffect(() => {
    if (selectedTeam && user) {
      fetchTeamDetails(selectedTeam);
      fetchTeamAnalytics(selectedTeam);
    }
  }, [selectedTeam, user]);

  const fetchTeams = async () => {
    if (!user?.id) return;

    try {
      setLoading(true);
      const data = await api.listTeams(user.id);
      setTeams(data.teams);
      if (data.teams.length > 0 && !selectedTeam) {
        setSelectedTeam(data.teams[0].id);
      }
    } catch (err: any) {
      console.error('Error fetching teams:', err);
    } finally {
      setLoading(false);
    }
  };

  const fetchTeamDetails = async (teamId: string) => {
    if (!user?.id) return;

    try {
      const data = await api.getTeamDetails(user.id, teamId);
      setTeamDetails(data);
    } catch (err: any) {
      console.error('Error fetching team details:', err);
    }
  };

  const fetchTeamAnalytics = async (teamId: string) => {
    if (!user?.id) return;

    try {
      const data = await api.getTeamAnalytics(user.id, teamId, 30);
      setTeamAnalytics(data);
    } catch (err: any) {
      console.error('Error fetching team analytics:', err);
    }
  };

  const handleCreateTeam = async () => {
    if (!user?.id || !newTeamName) return;

    try {
      await api.createTeam(user.id, newTeamName, newTeamDescription);
      setShowCreateModal(false);
      setNewTeamName('');
      setNewTeamDescription('');
      fetchTeams();
    } catch (err: any) {
      console.error('Error creating team:', err);
      alert('Failed to create team: ' + err.message);
    }
  };

  const getRoleBadgeColor = (role: string) => {
    switch (role) {
      case 'owner':
        return 'bg-[#D4AF37] text-black';
      case 'admin':
        return 'bg-blue-600 text-white';
      case 'member':
        return 'bg-gray-600 text-white';
      case 'viewer':
        return 'bg-gray-800 text-gray-300';
      default:
        return 'bg-gray-600 text-white';
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-black text-white p-8">
        <div className="max-w-6xl mx-auto">
          <h1 className="text-3xl font-bold mb-8 text-[#D4AF37]">Team Collaboration</h1>
          <p className="text-gray-400">Loading teams...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-black text-white p-8">
      <div className="max-w-6xl mx-auto">
        <div className="mb-8 flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-[#D4AF37] mb-2">Team Collaboration</h1>
            <p className="text-gray-400">Shared dashboards and team analytics</p>
          </div>
          <button
            onClick={() => setShowCreateModal(true)}
            className="px-4 py-2 bg-[#D4AF37] text-black rounded hover:bg-[#B8941F] font-semibold"
          >
            Create Team
          </button>
        </div>

        {teams.length === 0 ? (
          <Card>
            <CardContent>
              <div className="text-center py-12">
                <p className="text-gray-400 mb-4">You are not part of any teams yet.</p>
                <button
                  onClick={() => setShowCreateModal(true)}
                  className="px-6 py-3 bg-[#D4AF37] text-black rounded hover:bg-[#B8941F] font-semibold"
                >
                  Create Your First Team
                </button>
              </div>
            </CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
            {/* Team List */}
            <div className="md:col-span-1">
              <Card>
                <CardTitle>Your Teams</CardTitle>
                <CardContent>
                  <div className="space-y-2">
                    {teams.map((team) => (
                      <button
                        key={team.id}
                        onClick={() => setSelectedTeam(team.id)}
                        className={`w-full text-left p-3 rounded transition-colors ${
                          selectedTeam === team.id
                            ? 'bg-[#D4AF37] text-black'
                            : 'bg-gray-900 hover:bg-gray-800'
                        }`}
                      >
                        <p className="font-semibold">{team.name}</p>
                        <div className="flex items-center justify-between mt-1">
                          <span className={`text-xs px-2 py-1 rounded ${getRoleBadgeColor(team.role)}`}>
                            {team.role}
                          </span>
                          <span className="text-xs opacity-70">
                            {team.member_count} {team.member_count === 1 ? 'member' : 'members'}
                          </span>
                        </div>
                      </button>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Team Details */}
            <div className="md:col-span-3">
              {teamDetails && (
                <>
                  {/* Team Analytics */}
                  {teamAnalytics && (
                    <div className="mb-6">
                      <Card>
                        <CardTitle>Team Analytics (Last 30 Days)</CardTitle>
                        <CardContent>
                          <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-6">
                            <div>
                              <p className="text-gray-400 text-sm mb-1">Total Cost</p>
                              <p className="text-2xl font-bold text-[#D4AF37]">
                                ${teamAnalytics.team_totals.total_cost_dollars.toFixed(2)}
                              </p>
                            </div>
                            <div>
                              <p className="text-gray-400 text-sm mb-1">Total Tokens</p>
                              <p className="text-2xl font-bold">
                                {teamAnalytics.team_totals.total_tokens.toLocaleString()}
                              </p>
                            </div>
                            <div>
                              <p className="text-gray-400 text-sm mb-1">Total Requests</p>
                              <p className="text-2xl font-bold">
                                {teamAnalytics.team_totals.total_requests}
                              </p>
                            </div>
                            <div>
                              <p className="text-gray-400 text-sm mb-1">Success Rate</p>
                              <p className="text-2xl font-bold text-green-400">
                                {(100 - teamAnalytics.team_totals.error_rate_percent).toFixed(1)}%
                              </p>
                            </div>
                          </div>

                          {teamAnalytics.by_member.length > 0 && (
                            <div>
                              <h4 className="font-semibold mb-3">Usage by Member</h4>
                              <div className="space-y-2">
                                {teamAnalytics.by_member.map((member, idx) => (
                                  <div key={idx} className="bg-gray-900 p-4 rounded">
                                    <div className="grid grid-cols-4 gap-4 text-sm">
                                      <div>
                                        <p className="text-gray-400">User ID</p>
                                        <p className="font-mono text-xs truncate">{member.user_id.slice(0, 8)}...</p>
                                      </div>
                                      <div>
                                        <p className="text-gray-400">Cost</p>
                                        <p className="font-semibold text-[#D4AF37]">
                                          ${member.cost_dollars.toFixed(2)}
                                        </p>
                                      </div>
                                      <div>
                                        <p className="text-gray-400">Tokens</p>
                                        <p className="font-semibold">{member.tokens.toLocaleString()}</p>
                                      </div>
                                      <div>
                                        <p className="text-gray-400">Requests</p>
                                        <p className="font-semibold">{member.requests}</p>
                                      </div>
                                    </div>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                        </CardContent>
                      </Card>
                    </div>
                  )}

                  {/* Team Members */}
                  <Card>
                    <CardTitle>Team Members</CardTitle>
                    <CardContent>
                      <div className="space-y-3">
                        {teamDetails.members.map((member) => (
                          <div key={member.id} className="flex items-center justify-between bg-gray-900 p-4 rounded">
                            <div>
                              <p className="font-mono text-sm">{member.user_id}</p>
                              <p className="text-xs text-gray-400">
                                Joined {new Date(member.joined_at).toLocaleDateString()}
                              </p>
                            </div>
                            <span className={`px-3 py-1 rounded text-sm ${getRoleBadgeColor(member.role)}`}>
                              {member.role}
                            </span>
                          </div>
                        ))}
                      </div>

                      {(teamDetails.user_role === 'owner' || teamDetails.user_role === 'admin') && (
                        <div className="mt-6 pt-6 border-t border-gray-800">
                          <p className="text-sm text-gray-400 mb-2">
                            Add new members using the team management API
                          </p>
                        </div>
                      )}
                    </CardContent>
                  </Card>
                </>
              )}
            </div>
          </div>
        )}

        {/* Create Team Modal */}
        {showCreateModal && (
          <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
            <div className="bg-gray-900 rounded-lg p-6 max-w-md w-full">
              <h2 className="text-2xl font-bold mb-4 text-[#D4AF37]">Create New Team</h2>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium mb-2">Team Name</label>
                  <input
                    type="text"
                    value={newTeamName}
                    onChange={(e) => setNewTeamName(e.target.value)}
                    className="w-full px-4 py-2 bg-black border border-gray-700 rounded focus:outline-none focus:border-[#D4AF37]"
                    placeholder="My Awesome Team"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium mb-2">Description (Optional)</label>
                  <textarea
                    value={newTeamDescription}
                    onChange={(e) => setNewTeamDescription(e.target.value)}
                    className="w-full px-4 py-2 bg-black border border-gray-700 rounded focus:outline-none focus:border-[#D4AF37]"
                    placeholder="A short description of your team"
                    rows={3}
                  />
                </div>
              </div>

              <div className="flex gap-3 mt-6">
                <button
                  onClick={handleCreateTeam}
                  disabled={!newTeamName}
                  className="flex-1 px-4 py-2 bg-[#D4AF37] text-black rounded hover:bg-[#B8941F] font-semibold disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Create Team
                </button>
                <button
                  onClick={() => {
                    setShowCreateModal(false);
                    setNewTeamName('');
                    setNewTeamDescription('');
                  }}
                  className="px-4 py-2 bg-gray-800 rounded hover:bg-gray-700"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
