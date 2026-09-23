export type Profile = {
  id: string;
  client_id: string;
  name: string;
  tech_stacks: string[];
  skills: string[];
  notes: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type ProfileInput = {
  name: string;
  tech_stacks: string[];
  skills?: string[];
  notes?: string | null;
};

export type TechStack = {
  id: string;
  name: string;
  is_active: boolean;
  created_at: string;
};

export type ClientUser = {
  id: string;
  email: string;
  name: string;
  is_active: boolean;
  deleted_at: string | null;
  created_at: string;
};

export type BidderUser = {
  id: string;
  email: string;
  name: string;
  is_active: boolean;
  client_id: string;
  assigned_profile_id: string | null;
  created_at: string;
};

export type RoleCounts = {
  total: number;
  last_7_days: number;
  last_30_days: number;
};

export type DashboardCounts = {
  clients: RoleCounts;
  bidders: RoleCounts;
};
