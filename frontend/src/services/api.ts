// API Service Layer for backend endpoint management

export interface AutocompleteResult {
  id: string;
  name: string;
  coordinates: [number, number]; // [lat, lng]
}

export interface NavigateRequest {
  origin: [number, number];
  destination: [number, number];
  modes: string[];
}

export interface RouteSegment {
  instruction: string;
  distance: string;
  duration: string;
  coordinates: [number, number][];
  type: 'walk' | 'drive' | 'transit';
}

export interface Route {
  mode: string;
  totalDuration: string;
  totalDistance: string;
  segments: RouteSegment[];
  coordinates: [number, number][];
}

export interface NavigateResponse {
  routes: Route[];
}

export interface ReverseGeocodeRequest {
  coordinates: [number, number];
}

export interface ReverseGeocodeResponse {
  name: string;
  address: string;
}

export interface BusRouteGeometryRequest {
  origin: string;
  destination: string;
}

export interface BusRouteGeometryResponse {
  geometry: [number, number][];
  distance: string;
  duration: string;
}

export interface OperatorEvaluateRequest {
  modes: {
    type: 'on-demand' | 'bus' | 'on-demand+bus';
    config: any;
  }[];
}

export interface EvaluationMetrics {
  totalCoverage: string;
  estimatedCost: string;
  ridership: string;
  averageWaitTime: string;
  serviceHours: string;
}

export interface EvaluationResponse {
  success: boolean;
  message: string;
  metrics: EvaluationMetrics;
  coverageArea: [number, number][][]; // Polygon coordinates
  heatmapData: { coordinates: [number, number]; intensity: number }[];
  serviceBoundaries: [number, number][][]; // Multiple polygons
}

const apiBase = (import.meta.env.VITE_API_URL as string | undefined) ?? '';
const apiPrefix = (import.meta.env.VITE_API_PREFIX as string | undefined) ?? '/api';

const buildUrl = (path: string) => `${apiBase}${apiPrefix}${path}`;

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(buildUrl(path), {
    headers: { 'Content-Type': 'application/json', ...(options?.headers ?? {}) },
    ...options,
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed: ${response.status}`);
  }

  return (await response.json()) as T;
}

class ApiService {
  async autocomplete(query: string): Promise<AutocompleteResult[]> {
    if (!query) return [];
    const params = new URLSearchParams({ query });
    return request<AutocompleteResult[]>(`/autocomplete?${params.toString()}`);
  }

  async reverseGeocode(requestBody: ReverseGeocodeRequest): Promise<ReverseGeocodeResponse> {
    return request<ReverseGeocodeResponse>('/reverse-geocode', {
      method: 'POST',
      body: JSON.stringify(requestBody),
    });
  }

  async navigate(requestBody: NavigateRequest): Promise<NavigateResponse> {
    return request<NavigateResponse>('/navigate', {
      method: 'POST',
      body: JSON.stringify(requestBody),
    });
  }

  async getBusRouteGeometry(requestBody: BusRouteGeometryRequest): Promise<BusRouteGeometryResponse> {
    return request<BusRouteGeometryResponse>('/bus/geometry', {
      method: 'POST',
      body: JSON.stringify(requestBody),
    });
  }

  async evaluate(requestBody: OperatorEvaluateRequest): Promise<EvaluationResponse> {
    return request<EvaluationResponse>('/evaluate', {
      method: 'POST',
      body: JSON.stringify(requestBody),
    });
  }
}

export const apiService = new ApiService();
