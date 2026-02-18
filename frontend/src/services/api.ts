import { z } from 'zod';
import { createApiClient, schemas } from './client';

export type AutocompleteResult = z.infer<typeof schemas.AutocompleteResult>;
export type NavigateRequest = z.infer<typeof schemas.NavigateRequest>;
export type RouteSegment = z.infer<typeof schemas.RouteSegment>;
export type Route = z.infer<typeof schemas.Route>;
export type NavigateResponse = z.infer<typeof schemas.NavigateResponse>;
export type ReverseGeocodeRequest = z.infer<typeof schemas.ReverseGeocodeRequest>;
export type ReverseGeocodeResponse = z.infer<typeof schemas.ReverseGeocodeResponse>;
export type BusRouteGeometryRequest = z.infer<typeof schemas.BusRouteGeometryRequest>;
export type BusRouteGeometryResponse = z.infer<typeof schemas.BusRouteGeometryResponse>;
export type OperatorEvaluateRequest = z.infer<typeof schemas.OperatorEvaluateRequest>;
export type EvaluationMetrics = z.infer<typeof schemas.EvaluationMetrics>;
export type EvaluationResponse = z.infer<typeof schemas.EvaluationResponse>;
export type FixedLineRequest = z.infer<typeof schemas.FixedLineRequest>;
export type FixedLineResponse = z.infer<typeof schemas.FixedLineResponse>;
export type OnDemandRequest = z.infer<typeof schemas.OnDemandRequest>;
export type OnDemandResponse = z.infer<typeof schemas.OnDemandResponse>;
export type MultimodalResponse = z.infer<typeof schemas.MultimodalResponse>;
export type PrivateVehicleRequest = z.infer<typeof schemas.PrivateVehicleRequest>;
export type PrivateVehicleResponse = z.infer<typeof schemas.PrivateVehicleResponse>;
export type CreateDepotRequest = z.infer<typeof schemas.CreateDepotRequest>;
export type CreateDepotResponse = z.infer<typeof schemas.CreateDepotResponse>;
export type DepotSummary = z.infer<typeof schemas.DepotSummary>;
export type GtfsFeedListItem = z.infer<typeof schemas.GtfsFeedListItem>;
export type DemandListResponse = z.infer<typeof schemas.DemandListResponse>;

const apiBase =
  (import.meta.env.VITE_API_URL as string | undefined) ??
  (typeof window !== 'undefined' ? window.location.origin : '');
// The generated client includes the `/api` prefix in its paths.
const apiClient = createApiClient(apiBase || 'http://localhost:8000');

class ApiService {
  async autocomplete(query: string): Promise<AutocompleteResult[]> {
    if (!query) return [];
    return apiClient.autocomplete_api_autocomplete_get({ queries: { query } });
  }

  async reverseGeocode(requestBody: ReverseGeocodeRequest): Promise<ReverseGeocodeResponse> {
    return apiClient.reverse_geocode_api_reverse_geocode_post(requestBody);
  }

  async navigate(requestBody: NavigateRequest): Promise<NavigateResponse> {
    return apiClient.navigate_api_navigate_post(requestBody);
  }

  async getBusRouteGeometry(
    requestBody: BusRouteGeometryRequest
  ): Promise<BusRouteGeometryResponse> {
    return apiClient.bus_geometry_api_bus_geometry_post(requestBody);
  }

  async evaluate(requestBody: OperatorEvaluateRequest): Promise<EvaluationResponse> {
    return apiClient.evaluate_api_evaluate_post(requestBody);
  }

  async planFixedLine(requestBody: FixedLineRequest): Promise<FixedLineResponse> {
    console.log('[api] planFixedLine body:', requestBody);
    return apiClient.plan_fixed_line_api_plan_fixed_line_post(requestBody);
  }

  async planOnDemand(requestBody: OnDemandRequest): Promise<OnDemandResponse> {
    console.log('[api] planOnDemand body:', requestBody);
    return apiClient.plan_on_demand_api_plan_on_demand_post(requestBody);
  }

  async planMultimodal(requestBody: FixedLineRequest): Promise<MultimodalResponse> {
    console.log('[api] planMultimodal body:', requestBody);
    return apiClient.plan_multimodal_api_plan_multimodal_post(requestBody);
  }

  async planPrivateVehicle(requestBody: PrivateVehicleRequest): Promise<PrivateVehicleResponse> {
    console.log('[api] planPrivateVehicle body:', requestBody);
    return apiClient.plan_private_vehicle_api_plan_private_vehicle_post(requestBody);
  }

  async createDepot(requestBody: CreateDepotRequest): Promise<CreateDepotResponse> {
    console.log('[api] createDepot body:', requestBody);
    return apiClient.create_depot_api_on_demand_depots_post(requestBody);
  }

  async listOnDemandDepots(): Promise<DepotSummary[]> {
    return apiClient.list_on_demand_depots_api_on_demand_list_get();
  }

  async listGtfsFeeds(): Promise<GtfsFeedListItem[]> {
    return apiClient.list_gtfs_feeds_api_gtfs_list_get();
  }

  async listDemandModels(): Promise<DemandListResponse> {
    console.log('[api] GET /api/demand-list');
    return apiClient.demand_list_api_demand_list_get();
  }
}

export const apiService = new ApiService();
