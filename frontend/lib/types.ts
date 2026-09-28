/** A person the client bids as (e.g. "Lakeyth Terry"). Owns resume types and one Google Sheet. */
export type Profile = {
  id: string;
  client_id: string;
  name: string;
  notes: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type ProfileInput = {
  name: string;
  notes?: string | null;
};

/** One of a profile's resumes. Only its AI summary is stored, not the file. */
export type ResumeType = {
  id: string;
  client_id: string;
  profile_id: string;
  name: string;
  /** Key skills extracted from the uploaded resume. */
  skills: string[];
  resume_filename: string | null;
  resume_summary: string | null;
  resume_uploaded_at: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
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
