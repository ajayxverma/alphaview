export type RunStatus =
  | "queued"
  | "crawling"
  | "analyzing"
  | "enriching"
  | "synthesizing"
  | "completed"
  | "failed"
  | "cancelled";
 
export interface ResearchBudget {
  seconds: number; pages: number; queries: number; paid_calls: number; rounds: number; requests: number;
}

export interface ResearchOptions {
  mode: "quick" | "deep"; budget: ResearchBudget; language?: string; date_from?: string | null; date_to?: string | null;
  seed_urls?: string[]; preferred_domains?: string[]; excluded_domains?: string[];
}

export interface Place {
  label: string;
  lat: number;
  lon: number;
  country_code?: string | null;
  country?: string | null;
  region?: string | null;
  city?: string | null;
}

export interface Geo extends Place {
  radius_km: number;
}

export interface Run {
  id: string;
  query: string;
  sources: string[];
  geo: Geo | null;
  research_config?: ResearchOptions | null;
  status: RunStatus;
  signal_count: number;
  error: string | null;
  created_at: string;
  finished_at: string | null;
}

export interface Evidence {
  title: string;
  url: string;
  source: string;
  intent: string;
  sentiment: number;
  engagement: number;
  excerpt?: string;
  published_at?: string;
}

export interface Strategy {
  title: string;
  thesis: string;
  value_proposition: string;
  target_audience: string;
  wedge: string;
  execution_strategy: string[];
  go_to_market: string[];
  moat: string;
  risks: string[];
  kill_criteria: string[];
  key_takeaways: string[];
  generated_by: "llm" | "heuristic";
  model?: string | null;
  fallback_reason?: string | null;
}

export interface OpportunityMetrics {
  mentions: number;
  engagement: number;
  velocity: number;
  negative_sentiment: number;
  demand_intent_ratio: number;
  complaint_ratio: number;
  supply_ratio: number;
  unanswered_ratio: number;
  sources: Record<string, number>;
  components: Record<string, number>;
  external: Record<string, number>;
  connectors_used: string[];
}

export interface Opportunity {
  id: string;
  run_id: string;
  title: string;
  cluster_label: string;
  keywords: string[];
  gap_score: number;
  confidence: number;
  metrics: OpportunityMetrics;
  evidence: Evidence[];
  strategy: Strategy;
  created_at: string;
}

export interface RunDetail extends Run {
  opportunities: Opportunity[];
}

export interface FieldSpec {
  key: string;
  label: string;
  secret: boolean;
  required: boolean;
  help: string | null;
}

export interface Connector {
  id: string;
  name: string;
  description: string;
  auth_type: "api_key" | "oauth2";
  capabilities: string[];
  credential_fields: FieldSpec[];
  config_fields: FieldSpec[];
  available: boolean;
}

export interface Connection {
  id: string;
  provider: string;
  label: string;
  config: Record<string, string>;
  status: "active" | "error";
  last_error: string | null;
  created_at: string;
}

export type KeywordMetrics = Record<string, Record<string, number>>;

export interface AIProvider {
  id: string;
  name: string;
  default_model: string;
  models: string[];
  can_list_models: boolean;
  docs_url: string;
  credential_fields: FieldSpec[];
  config_fields: FieldSpec[];
}

export interface AICredential {
  id: string;
  provider: string;
  label: string;
  model: string;
  config: Record<string, string>;
  is_default: boolean;
  status: "active" | "error";
  last_error: string | null;
  created_at: string;
}
