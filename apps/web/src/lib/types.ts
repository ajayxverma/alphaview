export type RunStatus =
  | "queued"
  | "crawling"
  | "analyzing"
  | "enriching"
  | "synthesizing"
  | "completed"
  | "failed";

export interface Run {
  id: string;
  query: string;
  sources: string[];
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
