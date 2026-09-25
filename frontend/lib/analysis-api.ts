import { api } from "@/lib/api";

export type Seniority = "junior" | "mid" | "senior" | "lead" | "unknown";

export type RoleType = "backend" | "fullstack" | "mobile" | "frontend" | "data" | "devops" | "other";

export type AnalysisResult = {
  /** Absent on analyses saved before resume-based matching. */
  jd_summary?: string | null;
  role_type?: RoleType | null;
  /** Languages/frameworks the JD explicitly names (verified against the JD text). */
  jd_core_stack?: string[] | null;
  /** The job's core language/tech as the JD names it. */
  main_backend_skill: string;
  backend_framework: string | null;
  secondary_skills: string[];
  seniority: Seniority;
  key_requirements: string[];
  recommended_profile_id: string | null;
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
  recommended_profile_id: string | null;
  selected_profile_id: string | null;
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
  job_link?: string | null;
};

export type AnalyzeOutput = {
  result: AnalysisResult;
  model: string;
  prompt_version: string;
  tokens: number | null;
  latency_ms: number;
  duplicate_warning: boolean;
  duplicate_reason: string | null;
};

export type SaveAnalysisInput = AnalyzeInput & {
  selected_profile_id?: string | null;
  result: AnalysisResult;
  model: string;
  prompt_version: string;
  tokens?: number | null;
  latency_ms?: number | null;
};

export type AnalysisListParams = {
  search?: string;
  profile_id?: string;
  date_from?: string;
  date_to?: string;
};

export const analysisApi = {
  analyze: (input: AnalyzeInput) => api.post<AnalyzeOutput>("/analyses/analyze", input),
  save: (input: SaveAnalysisInput) => api.post<Analysis>("/analyses", input),
  list: (params?: AnalysisListParams) => {
    const query = new URLSearchParams();
    if (params?.search) query.set("search", params.search);
    if (params?.profile_id) query.set("profile_id", params.profile_id);
    if (params?.date_from) query.set("date_from", params.date_from);
    if (params?.date_to) query.set("date_to", params.date_to);
    const qs = query.toString();
    return api.get<Analysis[]>(`/analyses${qs ? `?${qs}` : ""}`);
  },
  get: (id: string) => api.get<Analysis>(`/analyses/${id}`),
  retry: (id: string) => api.post<Analysis>(`/analyses/${id}/retry`),
};
