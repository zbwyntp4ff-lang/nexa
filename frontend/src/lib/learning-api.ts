import { request } from "@/lib/api";

export interface LearningSettingsApi {
  memory_enabled: boolean;
  feedback_enabled: boolean;
  auto_knowledge_base: boolean;
  allow_cloud_on_documents: boolean;
  last_index_at: string | null;
  last_eval_at: string | null;
  last_eval_summary: string | null;
  updated_at: string;
}

export interface FeedbackStatsApi {
  total: number;
  by_rating: Record<string, number>;
  with_notes: number;
  positive_ratio: number | null;
  recurring_notes: string[];
  summary: string;
}

export interface LearningStatusApi {
  settings: LearningSettingsApi;
  memory_enabled: boolean;
  memory_item_count: number;
  knowledge_document_count: number;
  knowledge_chunk_hint: string;
  feedback_stats: FeedbackStatsApi;
  last_index_at: string | null;
  last_eval_at: string | null;
  last_eval_summary: string | null;
  mechanisms: string[];
  fine_tuning: {
    available_in_product: boolean;
    note: string;
    categories: Record<string, string>;
  };
  requires_confirmation: string[];
}

export interface ImprovementProposalApi {
  id: string;
  kind: string;
  title: string;
  rationale: string;
  suggested_change: string;
  status: string;
  before_summary: string | null;
  after_summary: string | null;
  improved: boolean | null;
  created_at: string;
  updated_at: string;
}

export function getLearningStatus(signal?: AbortSignal) {
  return request<LearningStatusApi>("/api/v1/learning/status", { signal });
}

export function updateLearningSettings(
  patch: Partial<
    Pick<
      LearningSettingsApi,
      | "memory_enabled"
      | "feedback_enabled"
      | "auto_knowledge_base"
      | "allow_cloud_on_documents"
    >
  >,
  signal?: AbortSignal,
) {
  return request<LearningSettingsApi>("/api/v1/learning/settings", {
    method: "PUT",
    body: JSON.stringify(patch),
    signal,
  });
}

export function runLearningEval(signal?: AbortSignal) {
  return request<FeedbackStatsApi>("/api/v1/learning/eval/run", {
    method: "POST",
    signal,
  });
}

export function listLearningProposals(signal?: AbortSignal) {
  return request<ImprovementProposalApi[]>("/api/v1/learning/proposals", { signal });
}

export function generateLearningProposals(signal?: AbortSignal) {
  return request<ImprovementProposalApi[]>("/api/v1/learning/proposals/generate", {
    method: "POST",
    signal,
  });
}

export function setLearningProposalStatus(
  id: string,
  status: "proposed" | "accepted" | "rejected" | "applied",
  signal?: AbortSignal,
) {
  return request<ImprovementProposalApi>(
    `/api/v1/learning/proposals/${encodeURIComponent(id)}/status`,
    {
      method: "POST",
      body: JSON.stringify({ status }),
      signal,
    },
  );
}

export type FeedbackRating =
  | "useful"
  | "not_useful"
  | "incorrect"
  | "incomplete"
  | "outdated"
  | "factual_error"
  | "code_error"
  | "missing_sources"
  | "off_topic"
  | "up"
  | "down";

export function submitAnswerFeedback(
  body: {
    rating: FeedbackRating;
    user_request: string;
    nexa_response: string;
    note?: string;
    conversation_id?: string;
    message_id?: string;
  },
  signal?: AbortSignal,
) {
  return request("/api/v1/knowledge-core/feedback", {
    method: "POST",
    body: JSON.stringify(body),
    signal,
  });
}
