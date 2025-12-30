-- Migration: Add Team Collaboration Features
-- Created: 2025-01-23
-- Description: Adds tables for team management and shared dashboards

-- ============================================================================
-- TEAMS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS va_teams (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    owner_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for fast lookup by owner
CREATE INDEX idx_va_teams_owner_id ON va_teams(owner_id);

-- ============================================================================
-- TEAM MEMBERS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS va_team_members (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    team_id UUID NOT NULL REFERENCES va_teams(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL CHECK (role IN ('owner', 'admin', 'member', 'viewer')),
    invited_by UUID REFERENCES auth.users(id),
    joined_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(team_id, user_id)
);

-- Indexes for fast lookup
CREATE INDEX idx_va_team_members_team_id ON va_team_members(team_id);
CREATE INDEX idx_va_team_members_user_id ON va_team_members(user_id);

-- ============================================================================
-- SHARED DASHBOARDS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS va_team_dashboards (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    team_id UUID NOT NULL REFERENCES va_teams(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    config JSONB DEFAULT '{}',
    shared_by UUID NOT NULL REFERENCES auth.users(id),
    is_public BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for fast lookup by team
CREATE INDEX idx_va_team_dashboards_team_id ON va_team_dashboards(team_id);

-- ============================================================================
-- DASHBOARD WIDGETS TABLE (Optional - for customizable dashboards)
-- ============================================================================
CREATE TABLE IF NOT EXISTS va_dashboard_widgets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    dashboard_id UUID NOT NULL REFERENCES va_team_dashboards(id) ON DELETE CASCADE,
    widget_type VARCHAR(100) NOT NULL,
    widget_config JSONB DEFAULT '{}',
    position_x INT DEFAULT 0,
    position_y INT DEFAULT 0,
    width INT DEFAULT 1,
    height INT DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for fast lookup by dashboard
CREATE INDEX idx_va_dashboard_widgets_dashboard_id ON va_dashboard_widgets(dashboard_id);

-- ============================================================================
-- ROW LEVEL SECURITY (RLS) POLICIES
-- ============================================================================

-- Enable RLS on all team tables
ALTER TABLE va_teams ENABLE ROW LEVEL SECURITY;
ALTER TABLE va_team_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE va_team_dashboards ENABLE ROW LEVEL SECURITY;
ALTER TABLE va_dashboard_widgets ENABLE ROW LEVEL SECURITY;

-- Teams: Users can see teams they own or are members of
CREATE POLICY "Users can view their teams"
    ON va_teams FOR SELECT
    USING (
        owner_id = auth.uid() OR
        id IN (SELECT team_id FROM va_team_members WHERE user_id = auth.uid())
    );

-- Teams: Only owners can create teams
CREATE POLICY "Users can create teams"
    ON va_teams FOR INSERT
    WITH CHECK (owner_id = auth.uid());

-- Teams: Only owners can update teams
CREATE POLICY "Owners can update teams"
    ON va_teams FOR UPDATE
    USING (owner_id = auth.uid());

-- Teams: Only owners can delete teams
CREATE POLICY "Owners can delete teams"
    ON va_teams FOR DELETE
    USING (owner_id = auth.uid());

-- Team Members: Users can view members of teams they belong to
CREATE POLICY "Users can view team members"
    ON va_team_members FOR SELECT
    USING (
        team_id IN (
            SELECT id FROM va_teams WHERE owner_id = auth.uid()
            UNION
            SELECT team_id FROM va_team_members WHERE user_id = auth.uid()
        )
    );

-- Team Members: Owners and admins can add members
CREATE POLICY "Owners and admins can add members"
    ON va_team_members FOR INSERT
    WITH CHECK (
        team_id IN (
            SELECT id FROM va_teams WHERE owner_id = auth.uid()
            UNION
            SELECT team_id FROM va_team_members
            WHERE user_id = auth.uid() AND role IN ('owner', 'admin')
        )
    );

-- Team Members: Owners and admins can update member roles
CREATE POLICY "Owners and admins can update members"
    ON va_team_members FOR UPDATE
    USING (
        team_id IN (
            SELECT id FROM va_teams WHERE owner_id = auth.uid()
            UNION
            SELECT team_id FROM va_team_members
            WHERE user_id = auth.uid() AND role IN ('owner', 'admin')
        )
    );

-- Team Members: Owners and admins can remove members
CREATE POLICY "Owners and admins can remove members"
    ON va_team_members FOR DELETE
    USING (
        team_id IN (
            SELECT id FROM va_teams WHERE owner_id = auth.uid()
            UNION
            SELECT team_id FROM va_team_members
            WHERE user_id = auth.uid() AND role IN ('owner', 'admin')
        )
    );

-- Team Dashboards: Team members can view dashboards
CREATE POLICY "Team members can view dashboards"
    ON va_team_dashboards FOR SELECT
    USING (
        team_id IN (
            SELECT id FROM va_teams WHERE owner_id = auth.uid()
            UNION
            SELECT team_id FROM va_team_members WHERE user_id = auth.uid()
        )
        OR is_public = TRUE
    );

-- Team Dashboards: Owners, admins, and members can create dashboards
CREATE POLICY "Team members can create dashboards"
    ON va_team_dashboards FOR INSERT
    WITH CHECK (
        team_id IN (
            SELECT id FROM va_teams WHERE owner_id = auth.uid()
            UNION
            SELECT team_id FROM va_team_members
            WHERE user_id = auth.uid() AND role IN ('owner', 'admin', 'member')
        )
    );

-- Team Dashboards: Creators and admins can update dashboards
CREATE POLICY "Creators and admins can update dashboards"
    ON va_team_dashboards FOR UPDATE
    USING (
        shared_by = auth.uid() OR
        team_id IN (
            SELECT id FROM va_teams WHERE owner_id = auth.uid()
            UNION
            SELECT team_id FROM va_team_members
            WHERE user_id = auth.uid() AND role IN ('owner', 'admin')
        )
    );

-- Team Dashboards: Creators and admins can delete dashboards
CREATE POLICY "Creators and admins can delete dashboards"
    ON va_team_dashboards FOR DELETE
    USING (
        shared_by = auth.uid() OR
        team_id IN (
            SELECT id FROM va_teams WHERE owner_id = auth.uid()
            UNION
            SELECT team_id FROM va_team_members
            WHERE user_id = auth.uid() AND role IN ('owner', 'admin')
        )
    );

-- Dashboard Widgets: Inherit permissions from parent dashboard
CREATE POLICY "Users can view dashboard widgets"
    ON va_dashboard_widgets FOR SELECT
    USING (
        dashboard_id IN (SELECT id FROM va_team_dashboards)
    );

CREATE POLICY "Users can manage dashboard widgets"
    ON va_dashboard_widgets FOR ALL
    USING (
        dashboard_id IN (
            SELECT id FROM va_team_dashboards
            WHERE shared_by = auth.uid() OR
            team_id IN (
                SELECT id FROM va_teams WHERE owner_id = auth.uid()
                UNION
                SELECT team_id FROM va_team_members
                WHERE user_id = auth.uid() AND role IN ('owner', 'admin')
            )
        )
    );

-- ============================================================================
-- FUNCTIONS AND TRIGGERS
-- ============================================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_team_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for teams table
CREATE TRIGGER update_va_teams_updated_at
    BEFORE UPDATE ON va_teams
    FOR EACH ROW
    EXECUTE FUNCTION update_team_updated_at();

-- Trigger for dashboards table
CREATE TRIGGER update_va_team_dashboards_updated_at
    BEFORE UPDATE ON va_team_dashboards
    FOR EACH ROW
    EXECUTE FUNCTION update_team_updated_at();

-- ============================================================================
-- SAMPLE DATA (Optional - for testing)
-- ============================================================================

-- Note: This migration is safe to run multiple times due to IF NOT EXISTS checks
-- The tables will only be created if they don't already exist
