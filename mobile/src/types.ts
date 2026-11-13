export type CriterionWeights = { rating: number; cost: number; proximity: number };
export type Participant = { label: string; value: string; delta_weight: number };
export type ParsedLocation = Participant & { lat: number | null; lng: number | null; error: string | null };
export type Category = 'cafe' | 'restaurant' | 'library' | 'park' | 'museum';
export type SearchInput = { city: string; category: Category; participants: Participant[] };
export type Preferences = {
  weights: CriterionWeights;
  minRating: number | null;
  maxMinutes: number | null;
  k: number;
};
export type RuntimeConfig = {
  production: boolean;
  max_participants: number;
  max_candidates: number;
  max_k: number;
  session_ttl_seconds: number;
  google_available: boolean;
  google_unavailable_reason: string;
  google_search_capacity?: { resolved_coordinates?: Record<string, { available: boolean; reason: string }> };
};
export type Health = { status: string; ai_status: string; ai_provider: string; ai_model: string; ai_ready: boolean };
export type Scenario = {
  id: string; session_only: boolean; city: string; category: Category;
  users: Array<{ id: string; label: string; delta_weight: number }>;
};
export type Candidate = {
  id: string; place_id: string; name: string; address: string; rating: number;
  review_count: number; price_level: number | null; provider: string;
  attributions: Array<{ provider: string; providerUri?: string }>;
};
export type RouteMetric = {
  candidate_id: string; user_id: string; duration_seconds: number; distance_meters: number; provider: string;
};
export type Recommendation = {
  rank: number; candidate: Candidate; score: number; t_avg_minutes: number; t_max_minutes: number;
  directions_url: string; cost_source: string;
  per_user: Array<{ user_id: string; label: string; raw_duration_minutes: number; distance_km: number }>;
  constraint_status: { complete_route_matrix: boolean };
  score_breakdown: {
    rating_component: number; cost_component: number; proximity_component: number;
    proximity_contributions: Array<{ user_id: string; label: string; weight: number; distance_km: number }>;
  };
};
export type RecommendationResponse = {
  scenario: Scenario; valid_alternatives: number; recommendations: Recommendation[]; criterion_weights: CriterionWeights;
};
export type Suggestion = {
  criterion_weights: CriterionWeights;
  participant_proximity_weights: Record<string, number>;
  min_rating: number | null; max_duration_minutes: number | null;
  explanation: string; warnings: string[]; source: string; model: string;
};
export type FeedbackReason = 'incorrect_preferences' | 'unsafe_response' | 'other';
