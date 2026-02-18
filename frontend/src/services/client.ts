import { makeApi, Zodios, type ZodiosOptions } from "@zodios/core";
import { z } from "zod";

const AutocompleteResult = z
  .object({
    id: z.string(),
    name: z.string(),
    coordinates: z.array(z.number()),
  })
  .passthrough();
const ValidationError = z
  .object({
    loc: z.array(z.union([z.string(), z.number()])),
    msg: z.string(),
    type: z.string(),
    input: z.unknown().optional(),
    ctx: z.object({}).partial().passthrough().optional(),
  })
  .passthrough();
const HTTPValidationError = z
  .object({ detail: z.array(ValidationError) })
  .partial()
  .passthrough();
const ReverseGeocodeRequest = z
  .object({ coordinates: z.array(z.number()).min(2).max(2) })
  .passthrough();
const ReverseGeocodeResponse = z
  .object({ name: z.string(), address: z.string() })
  .passthrough();
const NavigateRequest = z
  .object({
    origin: z.array(z.number()).min(2).max(2),
    destination: z.array(z.number()).min(2).max(2),
    modes: z.array(z.string()),
  })
  .passthrough();
const RouteSegment = z
  .object({
    instruction: z.string(),
    distance: z.string(),
    duration: z.string(),
    coordinates: z.array(z.array(z.number())),
    type: z.string(),
  })
  .passthrough();
const Route = z
  .object({
    mode: z.string(),
    totalDuration: z.string(),
    totalDistance: z.string(),
    segments: z.array(RouteSegment),
    coordinates: z.array(z.array(z.number())),
  })
  .passthrough();
const NavigateResponse = z.object({ routes: z.array(Route) }).passthrough();
const BusRouteGeometryRequest = z
  .object({ origin: z.string(), destination: z.string() })
  .passthrough();
const BusRouteGeometryResponse = z
  .object({
    geometry: z.array(z.array(z.number())),
    distance: z.string(),
    duration: z.string(),
  })
  .passthrough();
const OperatorEvaluateMode = z
  .object({ type: z.string(), config: z.object({}).partial().passthrough() })
  .passthrough();
const OperatorEvaluateRequest = z
  .object({ modes: z.array(OperatorEvaluateMode) })
  .passthrough();
const EvaluationMetrics = z
  .object({
    totalCoverage: z.string(),
    estimatedCost: z.string(),
    ridership: z.string(),
    averageWaitTime: z.string(),
    serviceHours: z.string(),
  })
  .passthrough();
const EvaluationResponse = z
  .object({
    success: z.boolean(),
    message: z.string(),
    metrics: EvaluationMetrics,
    coverageArea: z.array(z.array(z.array(z.number()))),
    heatmapData: z.array(z.object({}).partial().passthrough()),
    serviceBoundaries: z.array(z.array(z.array(z.number()))),
  })
  .passthrough();
const FixedLineRequest = z
  .object({
    origin: z.array(z.number()).min(2).max(2),
    destination: z.array(z.number()).min(2).max(2),
    depart_at_min: z.union([z.number(), z.null()]).optional(),
    arrive_by_min: z.union([z.number(), z.null()]).optional(),
    service_date: z.union([z.string(), z.null()]).optional(),
    agency_timezone: z.union([z.string(), z.null()]).optional(),
    max_walk_meters: z.number().int().optional().default(800),
    max_wait_minutes: z.union([z.number(), z.null()]).optional(),
    max_invehicle_minutes: z.union([z.number(), z.null()]).optional(),
    max_total_minutes: z.union([z.number(), z.null()]).optional(),
    transfer_limit: z.union([z.number(), z.null()]).optional(),
    score_weight_total_minutes: z.union([z.number(), z.null()]).optional(),
    score_weight_wait_minutes: z.union([z.number(), z.null()]).optional(),
    score_weight_walk_meters: z.union([z.number(), z.null()]).optional(),
    boc_request: z.union([z.boolean(), z.null()]).optional().default(false),
    multimodal_limit: z.union([z.number(), z.null()]).optional(),
    multimodal_number: z.union([z.number(), z.null()]).optional().default(3),
    force_taxi: z.union([z.boolean(), z.null()]).optional().default(false),
  })
  .passthrough();
const ScoreBreakdown = z
  .object({
    total_minutes: z.number(),
    wait_minutes: z.number(),
    walk_meters: z.number(),
    weight_total_minutes: z.number(),
    weight_wait_minutes: z.number(),
    weight_walk_meters: z.number(),
    score: z.number(),
  })
  .passthrough();
const Coordinate = z.object({ lat: z.number(), lon: z.number() }).passthrough();
const Leg = z
  .object({
    mode: z.string(),
    from_stop_id: z.union([z.string(), z.null()]).optional(),
    to_stop_id: z.union([z.string(), z.null()]).optional(),
    from_coords: z.union([Coordinate, z.null()]).optional(),
    to_coords: z.union([Coordinate, z.null()]).optional(),
    from_address: z.union([z.string(), z.null()]).optional(),
    to_address: z.union([z.string(), z.null()]).optional(),
    distance_m: z.union([z.number(), z.null()]).optional(),
    duration_s: z.union([z.number(), z.null()]).optional(),
    geometry: z.union([z.string(), z.null()]).optional(),
    route_id: z.union([z.string(), z.null()]).optional(),
    trip_id: z.union([z.string(), z.null()]).optional(),
  })
  .passthrough();
const Itinerary = z
  .object({
    itinerary_id: z.string(),
    legs: z.array(Leg),
    total_duration_s: z.number().int(),
    total_walk_m: z.number(),
    total_wait_s: z.number().int(),
    total_invehicle_s: z.number().int(),
    total_transit_distance_m: z.number().optional().default(0),
    total_vehicle_distance_m: z.number().optional().default(0),
    geometry: z.union([z.string(), z.null()]).optional(),
    score: ScoreBreakdown,
  })
  .passthrough();
const FixedLineResponse = z
  .object({
    best_itinerary: z.union([z.string(), z.null()]).optional(),
    total_duration_s: z.union([z.number(), z.null()]).optional(),
    total_wait_s: z.union([z.number(), z.null()]).optional(),
    total_invehicle_s: z.union([z.number(), z.null()]).optional(),
    total_walk_m: z.union([z.number(), z.null()]).optional(),
    total_transit_distance_m: z.union([z.number(), z.null()]).optional(),
    total_vehicle_distance_m: z.union([z.number(), z.null()]).optional(),
    score: z.union([ScoreBreakdown, z.null()]).optional(),
    itineraries: z.array(Itinerary),
    note: z.string(),
  })
  .passthrough();
const OnDemandRequest = z
  .object({
    origin: z.array(z.number()).min(2).max(2),
    destination: z.array(z.number()).min(2).max(2),
    passengers: z.number().int().optional().default(1),
    pickup_window_start_min: z.union([z.number(), z.null()]).optional(),
    pickup_window_end_min: z.union([z.number(), z.null()]).optional(),
    dropoff_window_end_min: z.union([z.number(), z.null()]).optional(),
    score_weight_total_minutes: z.union([z.number(), z.null()]).optional(),
    score_weight_wait_minutes: z.union([z.number(), z.null()]).optional(),
    score_weight_walk_meters: z.union([z.number(), z.null()]).optional(),
  })
  .passthrough();
const OnDemandResponse = z
  .object({
    vehicle_id: z.string(),
    eta_minutes: z.number().int(),
    distance_km: z.number(),
    total_duration_s: z.number().int(),
    total_wait_s: z.number().int(),
    total_invehicle_s: z.number().int(),
    total_walk_m: z.number(),
    total_transit_distance_m: z.number(),
    total_vehicle_distance_m: z.number(),
    itineraries: z.array(Itinerary),
    score: ScoreBreakdown,
    note: z.string(),
  })
  .passthrough();
const PrivateVehicleRequest = z
  .object({
    origin: z.array(z.number()).min(2).max(2),
    destination: z.array(z.number()).min(2).max(2),
    score_weight_total_minutes: z.union([z.number(), z.null()]).optional(),
    score_weight_wait_minutes: z.union([z.number(), z.null()]).optional(),
    score_weight_walk_meters: z.union([z.number(), z.null()]).optional(),
  })
  .passthrough();
const PrivateVehicleResponse = z
  .object({
    best_itinerary: z.union([z.string(), z.null()]).optional(),
    total_duration_s: z.union([z.number(), z.null()]).optional(),
    total_wait_s: z.union([z.number(), z.null()]).optional(),
    total_invehicle_s: z.union([z.number(), z.null()]).optional(),
    total_walk_m: z.union([z.number(), z.null()]).optional(),
    total_transit_distance_m: z.union([z.number(), z.null()]).optional(),
    total_vehicle_distance_m: z.union([z.number(), z.null()]).optional(),
    score: z.union([ScoreBreakdown, z.null()]).optional(),
    itineraries: z.array(Itinerary),
    note: z.string(),
  })
  .passthrough();
const OnDemandEvaluateRequest = z
  .object({
    vehicle_id: z.string(),
    score_weight_total_minutes: z.union([z.number(), z.null()]).optional(),
    score_weight_wait_minutes: z.union([z.number(), z.null()]).optional(),
    score_weight_walk_meters: z.union([z.number(), z.null()]).optional(),
  })
  .passthrough();
const OnDemandEvaluateResponse = z
  .object({
    vehicle_id: z.string(),
    stop_count: z.number().int(),
    total_duration_s: z.number().int(),
    total_wait_s: z.number().int(),
    total_invehicle_s: z.number().int(),
    total_distance_m: z.number(),
    score: ScoreBreakdown,
    note: z.string(),
  })
  .passthrough();
const OnDemandFulfillmentRequest = z
  .object({ vehicle_id: z.string() })
  .passthrough();
const OnDemandFulfillmentResponse = z
  .object({
    vehicle_id: z.string(),
    total_assigned: z.number().int(),
    fulfilled: z.number().int(),
    unfulfilled: z.number().int(),
    note: z.string(),
  })
  .passthrough();
const OnDemandSummaryResponse = z
  .object({
    total_requests: z.number().int(),
    assigned_requests: z.number().int(),
    unassigned_requests: z.number().int(),
    fulfilled_requests: z.number().int(),
    unfulfilled_requests: z.number().int(),
    assigned_pct: z.number(),
    fulfilled_pct: z.number(),
    note: z.string(),
  })
  .passthrough();
const OnDemandManifestRequest = z
  .object({ vehicle_id: z.string() })
  .passthrough();
const OnDemandManifestStop = z
  .object({
    sequence: z.number().int(),
    lat: z.number(),
    lon: z.number(),
    stop_type: z.union([z.string(), z.null()]).optional(),
    request_id: z.union([z.string(), z.null()]).optional(),
    window_start_min: z.union([z.number(), z.null()]).optional(),
    window_end_min: z.union([z.number(), z.null()]).optional(),
    planned_arrival_min: z.union([z.number(), z.null()]).optional(),
    planned_departure_min: z.union([z.number(), z.null()]).optional(),
  })
  .passthrough();
const OnDemandManifestLeg = z
  .object({
    mode: z.string(),
    from_stop_id: z.union([z.string(), z.null()]).optional(),
    to_stop_id: z.union([z.string(), z.null()]).optional(),
    from_coords: z.union([Coordinate, z.null()]).optional(),
    to_coords: z.union([Coordinate, z.null()]).optional(),
    from_address: z.union([z.string(), z.null()]).optional(),
    to_address: z.union([z.string(), z.null()]).optional(),
    distance_m: z.union([z.number(), z.null()]).optional(),
    duration_s: z.union([z.number(), z.null()]).optional(),
    geometry: z.union([z.string(), z.null()]).optional(),
    route_id: z.union([z.string(), z.null()]).optional(),
    trip_id: z.union([z.string(), z.null()]).optional(),
    from_sequence: z.number().int(),
    to_sequence: z.number().int(),
    from_lat: z.number(),
    from_lon: z.number(),
    to_lat: z.number(),
    to_lon: z.number(),
  })
  .passthrough();
const OnDemandManifestResponse = z
  .object({
    vehicle_id: z.string(),
    stop_count: z.number().int(),
    stops: z.array(OnDemandManifestStop),
    legs: z.array(OnDemandManifestLeg),
    geometry: z.union([z.string(), z.null()]),
    distance_m: z.union([z.number(), z.null()]),
    duration_s: z.union([z.number(), z.null()]),
    note: z.string(),
  })
  .passthrough();
const ItineraryMetrics = z
  .object({
    total_duration_s: z.number().int(),
    total_wait_s: z.number().int(),
    total_invehicle_s: z.number().int(),
    total_walk_m: z.number(),
    total_transit_distance_m: z.number(),
    total_vehicle_distance_m: z.number(),
    score: ScoreBreakdown,
  })
  .passthrough();
const MultimodalMetrics = z
  .object({
    overall: ItineraryMetrics,
    on_demand: ItineraryMetrics,
    fixed_line: ItineraryMetrics,
  })
  .passthrough();
const MultimodalItinerary = z
  .object({
    itinerary_id: z.string(),
    legs: z.array(Leg),
    metrics: MultimodalMetrics,
  })
  .passthrough();
const MultimodalResponse = z
  .object({
    best_itinerary: z.union([z.string(), z.null()]).optional(),
    total_duration_s: z.union([z.number(), z.null()]).optional(),
    total_wait_s: z.union([z.number(), z.null()]).optional(),
    total_invehicle_s: z.union([z.number(), z.null()]).optional(),
    total_walk_m: z.union([z.number(), z.null()]).optional(),
    total_transit_distance_m: z.union([z.number(), z.null()]).optional(),
    total_vehicle_distance_m: z.union([z.number(), z.null()]).optional(),
    score: z.union([ScoreBreakdown, z.null()]).optional(),
    itineraries: z.array(MultimodalItinerary),
    note: z.string(),
  })
  .passthrough();
const NearestStopsRequest = z
  .object({
    coordinates: z.array(z.number()).min(2).max(2),
    max_distance_m: z.number().optional().default(2000),
    limit: z.number().int().optional().default(10),
  })
  .passthrough();
const NearestStop = z
  .object({
    stop_id: z.string(),
    name: z.union([z.string(), z.null()]),
    lat: z.number(),
    lon: z.number(),
    distance_m: z.number(),
  })
  .passthrough();

export const schemas = {
  AutocompleteResult,
  ValidationError,
  HTTPValidationError,
  ReverseGeocodeRequest,
  ReverseGeocodeResponse,
  NavigateRequest,
  RouteSegment,
  Route,
  NavigateResponse,
  BusRouteGeometryRequest,
  BusRouteGeometryResponse,
  OperatorEvaluateMode,
  OperatorEvaluateRequest,
  EvaluationMetrics,
  EvaluationResponse,
  FixedLineRequest,
  ScoreBreakdown,
  Coordinate,
  Leg,
  Itinerary,
  FixedLineResponse,
  OnDemandRequest,
  OnDemandResponse,
  PrivateVehicleRequest,
  PrivateVehicleResponse,
  OnDemandEvaluateRequest,
  OnDemandEvaluateResponse,
  OnDemandFulfillmentRequest,
  OnDemandFulfillmentResponse,
  OnDemandSummaryResponse,
  OnDemandManifestRequest,
  OnDemandManifestStop,
  OnDemandManifestLeg,
  OnDemandManifestResponse,
  ItineraryMetrics,
  MultimodalMetrics,
  MultimodalItinerary,
  MultimodalResponse,
  NearestStopsRequest,
  NearestStop,
};

const endpoints = makeApi([
  {
    method: "get",
    path: "/api/autocomplete",
    alias: "autocomplete_api_autocomplete_get",
    description: `Search stop and depot names for autocomplete suggestions.`,
    requestFormat: "json",
    parameters: [
      {
        name: "query",
        type: "Query",
        schema: z.string().min(1),
      },
    ],
    response: z.array(AutocompleteResult),
    errors: [
      {
        status: 422,
        description: `Validation Error`,
        schema: HTTPValidationError,
      },
    ],
  },
  {
    method: "post",
    path: "/api/bus/geometry",
    alias: "bus_geometry_api_bus_geometry_post",
    description: `Mock bus route geometry generator.`,
    requestFormat: "json",
    parameters: [
      {
        name: "body",
        type: "Body",
        schema: BusRouteGeometryRequest,
      },
    ],
    response: BusRouteGeometryResponse,
    errors: [
      {
        status: 422,
        description: `Validation Error`,
        schema: HTTPValidationError,
      },
    ],
  },
  {
    method: "post",
    path: "/api/evaluate",
    alias: "evaluate_api_evaluate_post",
    description: `Mock operator evaluation endpoint.`,
    requestFormat: "json",
    parameters: [
      {
        name: "body",
        type: "Body",
        schema: OperatorEvaluateRequest,
      },
    ],
    response: EvaluationResponse,
    errors: [
      {
        status: 422,
        description: `Validation Error`,
        schema: HTTPValidationError,
      },
    ],
  },
  {
    method: "get",
    path: "/api/health",
    alias: "health_api_health_get",
    description: `Basic liveness check for the API service.`,
    requestFormat: "json",
    response: z.object({}).partial().passthrough(),
  },
  {
    method: "post",
    path: "/api/navigate",
    alias: "navigate_api_navigate_post",
    description: `Legacy navigation endpoint returning mock routes by mode.`,
    requestFormat: "json",
    parameters: [
      {
        name: "body",
        type: "Body",
        schema: NavigateRequest,
      },
    ],
    response: NavigateResponse,
    errors: [
      {
        status: 422,
        description: `Validation Error`,
        schema: HTTPValidationError,
      },
    ],
  },
  {
    method: "post",
    path: "/api/nearest-stops",
    alias: "nearest_stops_api_nearest_stops_post",
    description: `Return the nearest GTFS stops to a coordinate within a max distance.`,
    requestFormat: "json",
    parameters: [
      {
        name: "body",
        type: "Body",
        schema: NearestStopsRequest,
      },
    ],
    response: z.array(NearestStop),
    errors: [
      {
        status: 422,
        description: `Validation Error`,
        schema: HTTPValidationError,
      },
    ],
  },
  {
    method: "post",
    path: "/api/on-demand/evaluate",
    alias: "evaluate_on_demand_api_on_demand_evaluate_post",
    description: `Evaluate the active on-demand schedule for a vehicle and return aggregate metrics.`,
    requestFormat: "json",
    parameters: [
      {
        name: "body",
        type: "Body",
        schema: OnDemandEvaluateRequest,
      },
    ],
    response: OnDemandEvaluateResponse,
    errors: [
      {
        status: 422,
        description: `Validation Error`,
        schema: HTTPValidationError,
      },
    ],
  },
  {
    method: "post",
    path: "/api/on-demand/fulfillment",
    alias: "fulfillment_on_demand_api_on_demand_fulfillment_post",
    description: `Return fulfilled vs unfulfilled assigned requests for a vehicle.`,
    requestFormat: "json",
    parameters: [
      {
        name: "body",
        type: "Body",
        schema: z.object({ vehicle_id: z.string() }).passthrough(),
      },
    ],
    response: OnDemandFulfillmentResponse,
    errors: [
      {
        status: 422,
        description: `Validation Error`,
        schema: HTTPValidationError,
      },
    ],
  },
  {
    method: "post",
    path: "/api/on-demand/manifest",
    alias: "manifest_on_demand_api_on_demand_manifest_post",
    description: `Generate a route geometry for the active schedule of a vehicle.`,
    requestFormat: "json",
    parameters: [
      {
        name: "body",
        type: "Body",
        schema: z.object({ vehicle_id: z.string() }).passthrough(),
      },
    ],
    response: OnDemandManifestResponse,
    errors: [
      {
        status: 422,
        description: `Validation Error`,
        schema: HTTPValidationError,
      },
    ],
  },
  {
    method: "get",
    path: "/api/on-demand/summary",
    alias: "summary_on_demand_api_on_demand_summary_get",
    description: `Return totals and percentages for all on-demand requests.`,
    requestFormat: "json",
    response: OnDemandSummaryResponse,
  },
  {
    method: "post",
    path: "/api/plan/fixed-line",
    alias: "plan_fixed_line_api_plan_fixed_line_post",
    description: `Plan a fixed-line itinerary using GTFS schedules and walking access/egress.`,
    requestFormat: "json",
    parameters: [
      {
        name: "body",
        type: "Body",
        schema: FixedLineRequest,
      },
    ],
    response: FixedLineResponse,
    errors: [
      {
        status: 422,
        description: `Validation Error`,
        schema: HTTPValidationError,
      },
    ],
  },
  {
    method: "post",
    path: "/api/plan/multimodal",
    alias: "plan_multimodal_api_plan_multimodal_post",
    description: `Return fixed-line, on-demand, and multimodal combinations for the same OD request.`,
    requestFormat: "json",
    parameters: [
      {
        name: "body",
        type: "Body",
        schema: FixedLineRequest,
      },
    ],
    response: MultimodalResponse,
    errors: [
      {
        status: 422,
        description: `Validation Error`,
        schema: HTTPValidationError,
      },
    ],
  },
  {
    method: "post",
    path: "/api/plan/on-demand",
    alias: "plan_on_demand_api_plan_on_demand_post",
    description: `Assign an on-demand vehicle using insertion heuristic and persist the updated route.`,
    requestFormat: "json",
    parameters: [
      {
        name: "body",
        type: "Body",
        schema: OnDemandRequest,
      },
    ],
    response: OnDemandResponse,
    errors: [
      {
        status: 422,
        description: `Validation Error`,
        schema: HTTPValidationError,
      },
    ],
  },
  {
    method: "post",
    path: "/api/plan/private-vehicle",
    alias: "plan_private_vehicle_api_plan_private_vehicle_post",
    description: `Return a point-to-point private vehicle itinerary using OSRM routing.`,
    requestFormat: "json",
    parameters: [
      {
        name: "body",
        type: "Body",
        schema: PrivateVehicleRequest,
      },
    ],
    response: PrivateVehicleResponse,
    errors: [
      {
        status: 422,
        description: `Validation Error`,
        schema: HTTPValidationError,
      },
    ],
  },
  {
    method: "post",
    path: "/api/reverse-geocode",
    alias: "reverse_geocode_api_reverse_geocode_post",
    description: `Reverse geocoding for a coordinate using Nominatim.`,
    requestFormat: "json",
    parameters: [
      {
        name: "body",
        type: "Body",
        schema: ReverseGeocodeRequest,
      },
    ],
    response: ReverseGeocodeResponse,
    errors: [
      {
        status: 422,
        description: `Validation Error`,
        schema: HTTPValidationError,
      },
    ],
  },
]);

export const api = new Zodios(endpoints);

export function createApiClient(baseUrl: string, options?: ZodiosOptions) {
  return new Zodios(baseUrl, endpoints, options);
}
