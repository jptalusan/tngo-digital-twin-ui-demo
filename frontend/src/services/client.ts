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
const ItineraryMetrics = z
  .object({
    total_duration_s: z.number().int(),
    total_wait_s: z.number().int(),
    total_invehicle_s: z.number().int(),
    total_walk_m: z.number(),
    total_transit_distance_m: z.number(),
    total_vehicle_distance_m: z.number(),
    geometry: z.union([z.string(), z.null()]).optional(),
    score: ScoreBreakdown,
  })
  .passthrough();
const ResponseMetrics = z.object({ overall: ItineraryMetrics }).passthrough();
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
    metrics: z.union([ResponseMetrics, z.null()]).optional(),
    itineraries: z.array(Itinerary),
    note: z.string(),
  })
  .passthrough();
const CreateDepotRequest = z
  .object({
    coordinates: z.array(z.number()).min(2).max(2),
    address: z.union([z.string(), z.null()]).optional(),
    vehicles: z.number().int().gte(1),
    capacity: z.number().int().gte(1),
    service_zone_hex_ids: z.array(z.string()),
    h3_resolution: z.union([z.number(), z.null()]).optional(),
  })
  .passthrough();
const DepotVehicleSummary = z
  .object({ vehicle_id: z.string(), capacity: z.number().int() })
  .passthrough();
const CreateDepotResponse = z
  .object({
    depot_id: z.string(),
    name: z.string(),
    lat: z.number(),
    lon: z.number(),
    address: z.union([z.string(), z.null()]),
    vehicle_count: z.number().int(),
    capacity: z.number().int(),
    hex_count: z.number().int(),
    vehicles: z.array(DepotVehicleSummary),
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
    metrics: z.union([ResponseMetrics, z.null()]).optional(),
    note: z.string(),
  })
  .passthrough();
const VehicleSummary = z
  .object({
    vehicle_id: z.string(),
    capacity: z.number().int(),
    status: z.union([z.string(), z.null()]).optional(),
  })
  .passthrough();
const DepotSummary = z
  .object({
    depot_id: z.string(),
    name: z.string(),
    lat: z.number(),
    lon: z.number(),
    h3_ids: z.array(z.string()).optional().default([]),
    vehicles: z.array(VehicleSummary).optional().default([]),
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
    metrics: z.union([ResponseMetrics, z.null()]).optional(),
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
    metrics: z.union([ResponseMetrics, z.null()]).optional(),
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
const DemandSummary = z
  .object({ demand_name: z.string(), row_count: z.number().int() })
  .passthrough();
const DemandListResponse = z
  .object({ demands: z.array(DemandSummary) })
  .passthrough();
const Body_upload_gtfs_api_gtfs_upload_post = z
  .object({ gtfs_name: z.string(), file: z.instanceof(File) })
  .passthrough();
const GtfsUploadResponse = z
  .object({
    job_id: z.string(),
    gtfs_id: z.string(),
    gtfs_name: z.string(),
    status: z.string(),
  })
  .passthrough();
const GtfsJobStatus = z
  .object({
    job_id: z.string(),
    gtfs_id: z.string(),
    gtfs_name: z.string(),
    status: z.string(),
    error: z.union([z.string(), z.null()]),
    row_counts: z.union([z.object({}).partial().passthrough(), z.null()]),
    created_at: z.union([z.string(), z.null()]),
    updated_at: z.union([z.string(), z.null()]),
  })
  .passthrough();
const GtfsFeedListItem = z
  .object({ gtfs_id: z.string(), gtfs_name: z.string() })
  .passthrough();
const GtfsPreviewRouteGroup = z
  .object({ agency: z.string(), route_ids: z.array(z.string()) })
  .passthrough();
const GtfsPreviewStop = z
  .object({
    stop_id: z.string(),
    name: z.union([z.string(), z.null()]),
    lat: z.number(),
    lon: z.number(),
  })
  .passthrough();
const GtfsPreviewShapePoint = z
  .object({
    shape_id: z.string(),
    lat: z.number(),
    lon: z.number(),
    sequence: z.number().int(),
  })
  .passthrough();
const GtfsPreviewResponse = z
  .object({
    gtfs_id: z.string(),
    routes: z.array(GtfsPreviewRouteGroup),
    stops: z.array(GtfsPreviewStop),
    shape_points: z.array(GtfsPreviewShapePoint),
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
  ItineraryMetrics,
  ResponseMetrics,
  Coordinate,
  Leg,
  Itinerary,
  FixedLineResponse,
  CreateDepotRequest,
  DepotVehicleSummary,
  CreateDepotResponse,
  OnDemandRequest,
  OnDemandResponse,
  VehicleSummary,
  DepotSummary,
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
  MultimodalMetrics,
  MultimodalItinerary,
  MultimodalResponse,
  NearestStopsRequest,
  NearestStop,
  DemandSummary,
  DemandListResponse,
  Body_upload_gtfs_api_gtfs_upload_post,
  GtfsUploadResponse,
  GtfsJobStatus,
  GtfsFeedListItem,
  GtfsPreviewRouteGroup,
  GtfsPreviewStop,
  GtfsPreviewShapePoint,
  GtfsPreviewResponse,
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
    method: "get",
    path: "/api/demand-list",
    alias: "demand_list_api_demand_list_get",
    description: `Returns each distinct demand_name with the number of user rows loaded for that scenario.`,
    requestFormat: "json",
    response: DemandListResponse,
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
    path: "/api/gtfs/:gtfs_id/preview",
    alias: "preview_gtfs_api_gtfs__gtfs_id__preview_get",
    description: `Return a preview of routes, stops, and shape points for a GTFS feed.`,
    requestFormat: "json",
    parameters: [
      {
        name: "gtfs_id",
        type: "Path",
        schema: z.string(),
      },
      {
        name: "limit",
        type: "Query",
        schema: z.number().int().gte(1).lte(200).optional().default(10),
      },
    ],
    response: GtfsPreviewResponse,
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
    path: "/api/gtfs/jobs/:job_id",
    alias: "get_gtfs_job_api_gtfs_jobs__job_id__get",
    description: `Poll the status of an async GTFS upload job.`,
    requestFormat: "json",
    parameters: [
      {
        name: "job_id",
        type: "Path",
        schema: z.string(),
      },
    ],
    response: GtfsJobStatus,
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
    path: "/api/gtfs/list",
    alias: "list_gtfs_feeds_api_gtfs_list_get",
    description: `Return GTFS feeds for populating the operator view cards.`,
    requestFormat: "json",
    response: z.array(GtfsFeedListItem),
  },
  {
    method: "post",
    path: "/api/gtfs/upload",
    alias: "upload_gtfs_api_gtfs_upload_post",
    description: `Accept a GTFS zip file and a user-supplied name. Computes the MD5 hash of the file as gtfs_id. Returns 409 if the same file has already been uploaded. Processing runs in the background; poll GET /api/gtfs/jobs/{job_id} for status.`,
    requestFormat: "form-data",
    parameters: [
      {
        name: "body",
        type: "Body",
        schema: Body_upload_gtfs_api_gtfs_upload_post,
      },
    ],
    response: GtfsUploadResponse,
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
    path: "/api/on-demand/depots",
    alias: "create_depot_api_on_demand_depots_post",
    description: `Create a new depot with a homogeneous vehicle fleet and an H3-based service zone. Generates unique depot_id and vehicle_ids automatically.`,
    requestFormat: "json",
    parameters: [
      {
        name: "body",
        type: "Body",
        schema: CreateDepotRequest,
      },
    ],
    response: CreateDepotResponse,
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
    method: "get",
    path: "/api/on-demand/list",
    alias: "list_on_demand_depots_api_on_demand_list_get",
    description: `Return depots for populating the operator view cards.`,
    requestFormat: "json",
    response: z.array(DepotSummary),
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
