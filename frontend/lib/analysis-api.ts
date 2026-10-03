import { api } from "@/lib/api";

export type Seniority = "intern" | "junior" | "mid" | "senior" | "lead" | "unknown";
export type WorkArrangement = "remote" | "hybrid" | "onsite" | "unknown";
export type RemoteLocation = "us" | "worldwide" | "non_us" | "unknown";

export type RoleType = "backend" | "fullstack" | "mobile" | "frontend" | "data" | "devops" | "ai" | "other";

export type AnalysisResult = {
  /** Absent on analyses saved before resume-based matching. */
  jd_summary?: string | null;
  role_type?: RoleType | null;
  work_arrangement?: WorkArrangement | null;
  remote_location?: RemoteLocation | null;
  relocation_required?: boolean | null;
  /** The JD's own location wording, e.g. "Remote (US)". */
  location_note?: string | null;
  /** Why the job was skipped (junior/intern, or not US remote); such jobs can't be saved. */
  skip_reason?: string | null;
  /** Languages/frameworks the JD explicitly names (verified against the JD text). */
  jd_core_stack?: string[] | null;
  /** The job's core language/tech as the JD names it. */
  main_backend_skill: string;
  backend_framework: string | null;
  secondary_skills: string[];
  seniority: Seniority;
  key_requirements: string[];
  /** Best-fitting resume type within the chosen profile, or null for a "Dismatched JD". */
  recommended_resume_type_id?: string | null;
  confidence: number;
  reasoning: string;
};

export type RecordStatus = "PENDING" | "SUCCESS" | "FAILED" | "SKIPPED";

export type Analysis = {
  id: string;
  client_id: string;
  created_by: string;
  created_by_name: string;
  company_name: string;
  position_name: string;
  job_description: string;
  job_link: string | null;
  /** The profile (person) this JD was compared against. */
  profile_id: string | null;
  recommended_resume_type_id: string | null;
  selected_resume_type_id: string | null;
  result: AnalysisResult;
  model: string;
  prompt_version: string;
  tokens: number | null;
  latency_ms: number | null;
  record_status: RecordStatus;
  record_attempts: number;
  record_error: string | null;
  created_at: string;
};

export type AnalyzeInput = {
  company_name: string;
  position_name: string;
  job_description: string;
  job_link: string;
  /** Required for a client; ignored for a bidder (always their assigned profile). */
  profile_id?: string | null;
};

export type DuplicateCheckInput = Pick<
  AnalyzeInput,
  "company_name" | "position_name" | "job_link" | "profile_id"
>;

export type AnalyzeOutput = {
  result: AnalysisResult;
  model: string;
  prompt_version: string;
  tokens: number | null;
  latency_ms: number;
};

export type SaveAnalysisInput = AnalyzeInput & {
  selected_resume_type_id?: string | null;
  result: AnalysisResult;
  model: string;
  prompt_version: string;
  tokens?: number | null;
  latency_ms?: number | null;
};

export const analysisApi = {
  /** `duplicate` says where the job was already applied to; null when it's new. */
  checkDuplicate: (input: DuplicateCheckInput) =>
    api.post<{ duplicate: string | null }>("/analyses/check-duplicate", input),
  analyze: (input: AnalyzeInput) => api.post<AnalyzeOutput>("/analyses/analyze", input),
  save: (input: SaveAnalysisInput) => api.post<Analysis>("/analyses", input),
  get: (id: string) => api.get<Analysis>(`/analyses/${id}`),
  retry: (id: string) => api.post<Analysis>(`/analyses/${id}/retry`),
};
