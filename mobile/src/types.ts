export type CriterionWeights = { rating: number; cost: number; proximity: number };
export type UserConditions = {
  budget_limit: { amount: number; scope: 'per_person' | 'group'; currency: 'TRY' } | null;
  excluded_categories: Category[]; required_features: ('quiet' | 'accessible' | 'alcohol_free')[];
};
export type TravelMode = 'driving' | 'transit' | 'walking' | 'bicycling';
export type Participant = { label: string; value: string; delta_weight: number; travel_mode?: TravelMode | '' };
export type ParsedLocation = Participant & { lat: number | null; lng: number | null; error: string | null };
export type Category = string;
export type SearchInput = { city: string; category: Category; categories?: Category[]; travelMode?: TravelMode; participants: Participant[] };
export type Preferences = {
  weights: CriterionWeights;
  minRating: number | null;
  maxMinutes: number | null;
  k: number;
  conditions?: UserConditions;
};
export type RuntimeConfig = {
  capabilities?: { conditions_v1?: boolean; plan_context_v1?: boolean; group_invites_v1?: boolean; venue_types_v1?: boolean; travel_modes_v1?: boolean };
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
  per_user: Array<{ user_id: string; label: string; raw_duration_minutes: number; distance_km: number; travel_mode?: string }>;
  constraint_status: { complete_route_matrix: boolean };
  score_breakdown: {
    rating_component: number; cost_component: number; proximity_component: number;
    proximity_contributions: Array<{ user_id: string; label: string; weight: number; distance_km: number }>;
  };
};
export type RecommendationResponse = {
  scenario: Scenario; valid_alternatives: number; recommendations: Recommendation[]; criterion_weights: CriterionWeights;
  conditions?: UserConditions; warnings?: string[];
};
export type Suggestion = {
  criterion_weights: CriterionWeights;
  participant_proximity_weights: Record<string, number>;
  min_rating: number | null; max_duration_minutes: number | null;
  explanation: string; warnings: string[]; source: string; model: string;
  conditions?: UserConditions; questions?: string[];
};
export type FeedbackReason = 'incorrect_preferences' | 'unsafe_response' | 'other';
export type Group = { seats: { token:string; ready:boolean }[]; choices: { id:string; name:string; votes:number; provider:string; attributions:{provider:string}[] }[]; expires_in:number };
