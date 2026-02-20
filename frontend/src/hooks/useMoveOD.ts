import { useEffect, useRef, useState } from 'react';
import { createApiClient } from '../services/client';

const apiBase =
  (import.meta.env.VITE_API_URL as string | undefined) ??
  (typeof window !== 'undefined' ? window.location.origin : '');
const apiClient = createApiClient(apiBase || 'http://localhost:8000');

export type FeatureCollection = {
  type: 'FeatureCollection';
  features: any[];
};

export type Feature = {
  type: 'Feature';
  properties?: Record<string, any>;
  geometry: any;
};

export type SyntheticDemandItem = {
  origin_location?: { type: 'Point'; coordinates: [number, number] } | null;
  destination_location?: { type: 'Point'; coordinates: [number, number] } | null;
  origin_state_fips?: string;
  origin_county_fips?: string;
  destination_state_fips?: string;
  destination_county_fips?: string;
  travel_time_min?: number | null;
  travel_time_bin?: string | null;
  travel_distance_mi?: number | null;
  departure_time_utc?: string | null;
  arrival_time_utc?: string | null;
};

const normalizeFeatureCollection = (payload: any): FeatureCollection | null => {
  if (!payload) return null;
  if (payload.type === 'FeatureCollection' && Array.isArray(payload.features)) {
    return payload as FeatureCollection;
  }
  if (Array.isArray(payload.features)) {
    return { type: 'FeatureCollection', features: payload.features };
  }
  if (Array.isArray(payload.items)) {
    if (payload.items.length > 0 && payload.items[0]?.type === 'FeatureCollection') {
      return payload.items[0] as FeatureCollection;
    }
    return { type: 'FeatureCollection', features: payload.items };
  }
  return null;
};

const resolveErrorMessage = (error: unknown) => {
  if (!error) return 'Unknown error';
  if (typeof error === 'string') return error;
  if (error instanceof Error) return error.message;
  return 'Request failed';
};

export function useStatesGeometry() {
  const [data, setData] = useState<FeatureCollection | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);

    apiClient
      .list_state_geometries_api_states_geometry_get(undefined, { signal: controller.signal })
      .then((response: any) => {
        if (controller.signal.aborted) return;
        setData(normalizeFeatureCollection(response));
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setError(resolveErrorMessage(err));
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      });

    return () => controller.abort();
  }, []);

  return { data, loading, error };
}

export function useCountiesList(enabled = true) {
  const [data, setData] = useState<FeatureCollection | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    setLoading(true);
    setError(null);

    apiClient
      .moveod_counties_list_api_moveod_counties_list_get(undefined, { signal: controller.signal })
      .then((response: any) => {
        if (controller.signal.aborted) return;
        setData(normalizeFeatureCollection(response));
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setError(resolveErrorMessage(err));
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      });

    return () => controller.abort();
  }, [enabled]);

  return { data, loading, error };
}

export function useStatesSearch(query: string) {
  const [data, setData] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!query || query.trim().length < 2) {
      setData([]);
      setLoading(false);
      setError(null);
      return;
    }
    const controller = new AbortController();
    setLoading(true);
    setError(null);

    apiClient
      .search_states_api_states_search_get(
        { queries: { q: query.trim(), limit: 20 } },
        { signal: controller.signal }
      )
      .then((response: any) => {
        if (controller.signal.aborted) return;
        const items = Array.isArray(response?.items) ? response.items : [];
        setData(items);
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setError(resolveErrorMessage(err));
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      });

    return () => controller.abort();
  }, [query]);

  return { data, loading, error };
}

export function useCountiesByState(stateFips: string | null) {
  const cacheRef = useRef<Map<string, any[]>>(new Map());
  const [data, setData] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!stateFips) {
      setData([]);
      setLoading(false);
      setError(null);
      return;
    }

    const cached = cacheRef.current.get(stateFips);
    if (cached) {
      setData(cached);
      setLoading(false);
      setError(null);
      return;
    }

    const controller = new AbortController();
    setLoading(true);
    setError(null);

    apiClient
      .list_counties_api_states__state_fips__counties_get(
        { params: { state_fips: stateFips }, queries: { order: 'name' } },
        { signal: controller.signal }
      )
      .then((response: any) => {
        if (controller.signal.aborted) return;
        const items = Array.isArray(response?.items) ? response.items : [];
        cacheRef.current.set(stateFips, items);
        setData(items);
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setError(resolveErrorMessage(err));
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      });

    return () => controller.abort();
  }, [stateFips]);

  return { data, loading, error };
}

export function useCountiesGeometryByState(stateFips: string | null) {
  const cacheRef = useRef<Map<string, FeatureCollection>>(new Map());
  const [data, setData] = useState<FeatureCollection | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!stateFips) {
      setData(null);
      setLoading(false);
      setError(null);
      return;
    }

    const cached = cacheRef.current.get(stateFips);
    if (cached) {
      setData(cached);
      setLoading(false);
      setError(null);
      return;
    }

    const controller = new AbortController();
    setLoading(true);
    setError(null);

    apiClient
      .list_counties_api_states__state_fips__counties_get(
        { params: { state_fips: stateFips }, queries: { order: 'name', include_geometry: true } },
        { signal: controller.signal }
      )
      .then((response: any) => {
        if (controller.signal.aborted) return;
        const items = Array.isArray(response?.items) ? response.items : [];
        const features = items
          .map((item: any) => {
            if (!item?.geometry) return null;
            return {
              type: 'Feature',
              geometry: item.geometry,
              properties: {
                geoid: item.geoid,
                name: item.name,
                state_fips: item.state_fips,
                county_fips: item.county_fips
              }
            } as Feature;
          })
          .filter(Boolean) as Feature[];
        const collection: FeatureCollection = { type: 'FeatureCollection', features };
        cacheRef.current.set(stateFips, collection);
        setData(collection);
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setError(resolveErrorMessage(err));
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      });

    return () => controller.abort();
  }, [stateFips]);

  return { data, loading, error };
}

export function useCountiesSearch(query: string, stateFips: string | null) {
  const [data, setData] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!stateFips || !query || query.trim().length < 2) {
      setData([]);
      setLoading(false);
      setError(null);
      return;
    }

    const controller = new AbortController();
    setLoading(true);
    setError(null);

    apiClient
      .search_counties_api_counties_search_get(
        { queries: { q: query.trim(), state_fips: stateFips, limit: 20 } },
        { signal: controller.signal }
      )
      .then((response: any) => {
        if (controller.signal.aborted) return;
        const items = Array.isArray(response?.items) ? response.items : [];
        setData(items);
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setError(resolveErrorMessage(err));
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      });

    return () => controller.abort();
  }, [query, stateFips]);

  return { data, loading, error };
}

export function useCountyGeometry(geoid: string | null) {
  const cacheRef = useRef<Map<string, Feature | FeatureCollection>>(new Map());
  const [data, setData] = useState<Feature | FeatureCollection | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!geoid) {
      setData(null);
      setLoading(false);
      setError(null);
      return;
    }

    const cached = cacheRef.current.get(geoid);
    if (cached) {
      setData(cached);
      setLoading(false);
      setError(null);
      return;
    }

    const controller = new AbortController();
    setLoading(true);
    setError(null);

    apiClient
      .get_county_geometry_api_counties_geometry_get(
        { queries: { geoid } },
        { signal: controller.signal }
      )
      .then((response: any) => {
        if (controller.signal.aborted) return;
        const item = response?.item ?? null;
        if (item) {
          cacheRef.current.set(geoid, item);
          setData(item);
        } else {
          setData(null);
        }
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setError(resolveErrorMessage(err));
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      });

    return () => controller.abort();
  }, [geoid]);

  return { data, loading, error };
}

export function useSyntheticDemand(
  stateFips: string | null,
  countyFips: string | null,
  limit = 500,
  enabled = true
) {
  const [data, setData] = useState<SyntheticDemandItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!enabled || !stateFips || !countyFips) {
      setData([]);
      setLoading(false);
      setError(null);
      return;
    }

    const controller = new AbortController();
    setLoading(true);
    setError(null);

    apiClient
      .get_synthetic_demand_api_moveod_synthetic_demand_get(
        { queries: { state_fips: stateFips, county_fips: countyFips, limit } },
        { signal: controller.signal }
      )
      .then((response: any) => {
        if (controller.signal.aborted) return;
        const items = Array.isArray(response?.items) ? response.items : [];
        setData(items);
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setError(resolveErrorMessage(err));
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      });

    return () => controller.abort();
  }, [stateFips, countyFips, limit, enabled]);

  return { data, loading, error };
}
