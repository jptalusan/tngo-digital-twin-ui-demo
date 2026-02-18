import { useState, useCallback, useMemo, useEffect } from 'react';
import { MapView, Marker, RoutePolyline, MapLayer } from './components/MapView';
import { PassengerView } from './components/PassengerView';
import { OperatorView, Depot, BusRoute } from './components/OperatorView';
import { EvaluationDrawer } from './components/EvaluationDrawer';
import { ItineraryDrawer } from './components/ItineraryDrawer';
import { MapLegend, LegendItem } from './components/MapLegend';
import { MapContextMenu } from './components/MapContextMenu';
import { apiService, AutocompleteResult, Route, EvaluationResponse } from './services/api';
import { buildUrl } from './services/http';
import * as h3 from 'h3-js';

type ViewMode = 'passenger' | 'operator';
type DepotWizardStep = 'pick-location' | 'select-zone' | 'vehicles';

export default function App() {
  const [viewMode, setViewMode] = useState<ViewMode>('passenger');
  const [origin, setOrigin] = useState<AutocompleteResult | null>(null);
  const [destination, setDestination] = useState<AutocompleteResult | null>(null);
  const [routes, setRoutes] = useState<Route[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedRouteIndex, setSelectedRouteIndex] = useState<number>(0);
  const [highlightedSegment, setHighlightedSegment] = useState<[number, number][] | undefined>();
  const [depots, setDepots] = useState<Depot[]>([]);
  const [busRoutes, setBusRoutes] = useState<BusRoute[]>([]);
  const [evaluationResult, setEvaluationResult] = useState<EvaluationResponse | null>(null);
  const [showEvaluationDrawer, setShowEvaluationDrawer] = useState(false);
  const [evaluating, setEvaluating] = useState(false);
  const [legendItems, setLegendItems] = useState<LegendItem[]>([]);
  const [contextMenu, setContextMenu] = useState<{ x: number; y: number; coordinates: [number, number] } | null>(null);
  const [itineraryDrawerOpen, setItineraryDrawerOpen] = useState(true);
  const [itineraryBestId, setItineraryBestId] = useState<string | null>(null);
  const [itineraries, setItineraries] = useState<any[]>([]);
  const [itineraryMode, setItineraryMode] = useState<string>('');
  const [selectedItineraryId, setSelectedItineraryId] = useState<string | null>(null);
  const [baseMapStyle, setBaseMapStyle] = useState<'standard' | 'light'>('standard');
  const [depotWizardOpen, setDepotWizardOpen] = useState(false);
  const [depotWizardStep, setDepotWizardStep] = useState<DepotWizardStep>('pick-location');
  const [draftDepotLocation, setDraftDepotLocation] = useState<{ coords: [number, number]; address?: string } | null>(null);
  const [draftDepotHexes, setDraftDepotHexes] = useState<string[]>([]);
  const [draftDepotVehicles, setDraftDepotVehicles] = useState(5);
  const [draftDepotCapacity, setDraftDepotCapacity] = useState(4);
  const [depotGeocoding, setDepotGeocoding] = useState(false);
  const [depotZoneError, setDepotZoneError] = useState<string | null>(null);
  const [selectedDepotId, setSelectedDepotId] = useState<string | null>(null);
  const [wizardPinnedHex, setWizardPinnedHex] = useState<string | null>(null);
  const [showDepotHexes, setShowDepotHexes] = useState(false);
  const [gtfsUploads, setGtfsUploads] = useState<Array<{ gtfs_id: string; gtfs_name: string; job_id: string; status: string }>>([]);
  const [gtfsPreview, setGtfsPreview] = useState<{
    gtfs_id: string;
    routes: Array<{ agency: string; route_ids: string[] }>;
    stops: Array<{ stop_id: string; name: string | null; lat: number; lon: number }>;
    shape_points: Array<{ shape_id: string; lat: number; lon: number; sequence: number }>;
  } | null>(null);
  const [gtfsPreviewLoadingId, setGtfsPreviewLoadingId] = useState<string | null>(null);

  const mapLoading = loading || evaluating;
  const loadingLabel = loading ? 'Loading routes...' : 'Evaluating service...';
  const orderItineraries = useCallback((items: any[], bestId?: string | null) => {
    if (!bestId) return items;
    const index = items.findIndex((it) => it?.itinerary_id === bestId);
    if (index <= 0) return items;
    const next = [...items];
    const [best] = next.splice(index, 1);
    next.unshift(best);
    return next;
  }, []);
  const decodePolyline = useCallback((encoded: string): [number, number][] => {
    let index = 0;
    let lat = 0;
    let lng = 0;
    const coordinates: [number, number][] = [];

    while (index < encoded.length) {
      let result = 0;
      let shift = 0;
      let byte = 0;
      do {
        byte = encoded.charCodeAt(index++) - 63;
        result |= (byte & 0x1f) << shift;
        shift += 5;
      } while (byte >= 0x20);
      const deltaLat = (result & 1) ? ~(result >> 1) : result >> 1;
      lat += deltaLat;

      result = 0;
      shift = 0;
      do {
        byte = encoded.charCodeAt(index++) - 63;
        result |= (byte & 0x1f) << shift;
        shift += 5;
      } while (byte >= 0x20);
      const deltaLng = (result & 1) ? ~(result >> 1) : result >> 1;
      lng += deltaLng;

      coordinates.push([lat / 1e5, lng / 1e5]);
    }
    return coordinates;
  }, []);

  const extractItineraryGeometry = useCallback(
    (itinerary: any): [number, number][] | null => {
      if (!itinerary) return null;
      if (typeof itinerary.geometry === 'string' && itinerary.geometry.length > 0) {
        return decodePolyline(itinerary.geometry);
      }
      const legs = Array.isArray(itinerary.legs) ? itinerary.legs : [];
      const merged: [number, number][] = [];
      legs.forEach((leg: any) => {
        if (typeof leg?.geometry === 'string' && leg.geometry.length > 0) {
          const points = decodePolyline(leg.geometry);
          if (points.length === 0) return;
          if (merged.length > 0 && merged[merged.length - 1][0] === points[0][0] && merged[merged.length - 1][1] === points[0][1]) {
            merged.push(...points.slice(1));
          } else {
            merged.push(...points);
          }
        }
      });
      return merged.length > 0 ? merged : null;
    },
    [decodePolyline]
  );

  const logItineraryGeometries = useCallback((label: string, items: any[]) => {
    const summary = items.map((it: any, idx: number) => {
      const geometryString = typeof it?.geometry === 'string' ? it.geometry : '';
      const legGeometries = Array.isArray(it?.legs)
        ? it.legs.filter((leg: any) => typeof leg?.geometry === 'string' && leg.geometry.length > 0).length
        : 0;
      const geometryPoints = geometryString ? decodePolyline(geometryString).length : 0;
      return {
        index: idx,
        itinerary_id: it?.itinerary_id ?? '(none)',
        geometry_len: geometryString.length,
        geometry_points: geometryPoints,
        geometry_prefix: geometryString.slice(0, 12),
        leg_geometries: legGeometries
      };
    });
    console.table(summary);
    console.log(`[navigate] ${label} geometry summary`, summary);
  }, [decodePolyline]);
  const formatCoordinates = (coordinates: [number, number]) =>
    `${coordinates[0].toFixed(5)}, ${coordinates[1].toFixed(5)}`;
  const truncateAddress = (address: string) => {
    const parts = address.split(',').map((part) => part.trim()).filter(Boolean);
    if (parts.length <= 4) return parts.join(', ');
    return parts.slice(0, 4).join(', ');
  };
  const startDepotWizard = useCallback((defaults: { vehicles: number; capacity: number }) => {
    setDepotWizardOpen(true);
    setDepotWizardStep('pick-location');
    setDraftDepotLocation(null);
    setDraftDepotHexes([]);
    setDraftDepotVehicles(defaults.vehicles);
    setDraftDepotCapacity(defaults.capacity);
    setDepotZoneError(null);
    setWizardPinnedHex(null);
    setShowDepotHexes(true);
  }, []);

  const closeDepotWizard = useCallback(() => {
    setDepotWizardOpen(false);
    setDepotWizardStep('pick-location');
    setDraftDepotLocation(null);
    setDraftDepotHexes([]);
    setDepotZoneError(null);
    setWizardPinnedHex(null);
  }, []);

  const getHexNeighbors = useCallback((hexId: string) => {
    const gridDisk = (h3 as any).gridDisk ?? (h3 as any).kRing;
    if (!gridDisk) return [];
    try {
      return gridDisk(hexId, 1) as string[];
    } catch (error) {
      console.warn('[hex] failed to fetch neighbors', error);
      return [];
    }
  }, []);

  const isHexSelectionContiguous = useCallback((hexes: string[]) => {
    if (hexes.length <= 1) return true;
    const set = new Set(hexes);
    const visited = new Set<string>();
    const stack = [hexes[0]];
    visited.add(hexes[0]);
    while (stack.length > 0) {
      const current = stack.pop()!;
      const neighbors = getHexNeighbors(current);
      neighbors.forEach((neighbor) => {
        if (set.has(neighbor) && !visited.has(neighbor)) {
          visited.add(neighbor);
          stack.push(neighbor);
        }
      });
    }
    return visited.size === set.size;
  }, [getHexNeighbors]);

  const toggleDepotHex = useCallback((hexId: string) => {
    setDraftDepotHexes((prev) => {
      const next = new Set(prev);
      if (wizardPinnedHex && hexId === wizardPinnedHex) {
        return prev;
      }
      if (next.has(hexId)) {
        next.delete(hexId);
        setDepotZoneError(null);
        return Array.from(next);
      }
      if (next.size === 0) {
        next.add(hexId);
        setDepotZoneError(null);
        return Array.from(next);
      }
      const neighbors = getHexNeighbors(hexId).filter((neighbor) => neighbor !== hexId);
      const isAdjacent = neighbors.some((neighbor) => next.has(neighbor));
      if (!isAdjacent) {
        setDepotZoneError('Selection must be contiguous (touching sides only).');
        return prev;
      }
      next.add(hexId);
      setDepotZoneError(null);
      return Array.from(next);
    });
  }, [getHexNeighbors, wizardPinnedHex]);

  const gtfsMarkers = useMemo(() => {
    if (!gtfsPreview) return [];
    return gtfsPreview.stops.map((stop) => ({
      id: `gtfs-stop-${stop.stop_id}`,
      coordinates: [stop.lat, stop.lon] as [number, number],
      type: 'gtfs-stop' as const,
      description: stop.name ?? undefined
    }));
  }, [gtfsPreview]);
  const gtfsRoutes = useMemo(() => {
    if (!gtfsPreview) return [];
    const grouped = new Map<string, Array<{ lat: number; lon: number; sequence: number }>>();
    gtfsPreview.shape_points.forEach((point) => {
      const list = grouped.get(point.shape_id) ?? [];
      list.push(point);
      grouped.set(point.shape_id, list);
    });
    const routes: RoutePolyline[] = [];
    grouped.forEach((points, shapeId) => {
      const sorted = points.sort((a, b) => a.sequence - b.sequence);
      if (sorted.length < 2) return;
      const maxPoints = 200;
      const step = Math.max(1, Math.ceil(sorted.length / maxPoints));
      const sampled = sorted.filter((_, index) => index % step === 0);
      if (sampled.length < 2) return;
      routes.push({
        id: `gtfs-shape-${shapeId}`,
        coordinates: sampled.map((point) => [point.lat, point.lon] as [number, number]),
        color: '#f97316',
        weight: 4,
        opacity: 0.75,
        outlineColor: '#0f172a',
        outlineWeight: 7,
        outlineOpacity: 0.7
      });
    });
    return routes;
  }, [gtfsPreview]);

  // Generate markers for map
  const markers = useMemo(() => {
    const m: Marker[] = [];
    if (viewMode === 'passenger') {
      if (origin) {
        m.push({
          id: 'origin',
          coordinates: origin.coordinates,
          type: 'origin',
          description: origin.name
        });
      }
      if (destination) {
        m.push({
          id: 'destination',
          coordinates: destination.coordinates,
          type: 'destination',
          description: destination.name
        });
      }
    } else {
      depots.forEach((depot, index) => {
        m.push({
          id: depot.id,
          coordinates: depot.coordinates,
          type: 'depot',
          label: `D${index + 1}`
        });
      });
      if (depotWizardOpen && draftDepotLocation) {
        m.push({
          id: 'draft-depot',
          coordinates: draftDepotLocation.coords,
          type: 'depot',
          label: 'D*'
        });
      }
      if (!depotWizardOpen && selectedDepotId) {
        const selected = depots.find((depot) => depot.id === selectedDepotId);
        if (selected) {
          m.push({
            id: `selected-${selected.id}`,
            coordinates: selected.coordinates,
            type: 'depot',
            label: 'D'
          });
        }
      }
      m.push(...gtfsMarkers);
    }
    return m;
  }, [viewMode, origin, destination, depots, depotWizardOpen, draftDepotLocation, selectedDepotId, gtfsMarkers]);
  const depotHexes = useMemo(
    () => depots.flatMap((depot) => depot.serviceZoneHexes ?? []),
    [depots]
  );
  const activeDepotHexes = useMemo(() => {
    if (!selectedDepotId) return [];
    return depots.find((depot) => depot.id === selectedDepotId)?.serviceZoneHexes ?? [];
  }, [depots, selectedDepotId]);

  useEffect(() => {
    if (itineraries.length === 0) {
      setSelectedItineraryId(null);
      return;
    }
    const best = itineraryBestId ?? itineraries[0]?.itinerary_id ?? null;
    setSelectedItineraryId(best);
  }, [itineraries, itineraryBestId]);

  const selectedItinerary = useMemo(() => {
    if (!selectedItineraryId) return null;
    return itineraries.find((it) => it?.itinerary_id === selectedItineraryId) ?? null;
  }, [itineraries, selectedItineraryId]);

  // Generate route polylines for map
  const routePolylines = useMemo(() => {
    const polylines: RoutePolyline[] = [];
    if (viewMode === 'passenger' && routes.length > 0) {
      // Darker, more visible colors (Tailwind 700 shades)
      const colors = ['#1d4ed8', '#047857', '#b45309', '#b91c1c', '#6d28d9'];
      routes.forEach((route, index) => {
        polylines.push({
          id: route.mode,
          coordinates: route.coordinates,
          color: colors[index % colors.length],
          weight: 6,
          opacity: index === selectedRouteIndex ? 1.0 : 0.5
        });
      });
    }

    // Generate bus route polylines (operator view)
    if (viewMode === 'operator' && busRoutes.length > 0) {
      busRoutes.forEach((route) => {
        if (route.geometry && route.geometry.length > 0) {
          polylines.push({
            id: route.id,
            coordinates: route.geometry,
            color: '#1d4ed8',
            weight: 6,
            opacity: 0.8
          });
        }
      });
    }

    if (viewMode === 'passenger' && itineraries.length > 0) {
      itineraries.forEach((itinerary, index) => {
        const geometry = extractItineraryGeometry(itinerary);
        if (!geometry || geometry.length === 0) return;
        const isSelected = selectedItineraryId
          ? itinerary?.itinerary_id === selectedItineraryId
          : index === 0;
        polylines.push({
          id: `itinerary-${itinerary?.itinerary_id ?? index}`,
          coordinates: geometry,
          color: isSelected ? '#3b82f6' : '#64748b',
          weight: isSelected ? 6 : 5,
          opacity: isSelected ? 0.95 : 0.75,
          outlineColor: isSelected ? '#1e3a8a' : '#334155',
          outlineWeight: isSelected ? 10 : 8,
          outlineOpacity: isSelected ? 0.95 : 0.7
        });
      });
    }
    if (viewMode === 'operator' && gtfsRoutes.length > 0) {
      polylines.push(...gtfsRoutes);
    }
    return polylines;
  }, [
    viewMode,
    routes,
    selectedRouteIndex,
    busRoutes,
    itineraries,
    selectedItineraryId,
    selectedItinerary,
    extractItineraryGeometry,
    gtfsRoutes
  ]);

  // Map layers for evaluation
  const mapLayers = useMemo(() => {
    const layers: MapLayer[] = [];
    if (evaluationResult && viewMode === 'operator') {
      const coverageLayer = legendItems.find(item => item.id === 'coverage');
      const heatmapLayer = legendItems.find(item => item.id === 'heatmap');
      const boundaryLayer = legendItems.find(item => item.id === 'boundary');

      if (coverageLayer?.visible) {
        layers.push({
          id: 'coverage',
          type: 'polygon',
          data: evaluationResult.coverageArea,
          visible: true
        });
      }
      if (heatmapLayer?.visible) {
        layers.push({
          id: 'heatmap',
          type: 'heatmap',
          data: evaluationResult.heatmapData,
          visible: true
        });
      }
      if (boundaryLayer?.visible) {
        layers.push({
          id: 'boundary',
          type: 'boundary',
          data: evaluationResult.serviceBoundaries,
          visible: true
        });
      }
    }
    return layers;
  }, [viewMode, evaluationResult, legendItems]);

  const handleNavigate = async (
    mode: 'on-demand' | 'bus' | 'car+bus' | 'car',
    payload: { origin: [number, number]; destination: [number, number] }
  ) => {
    setLoading(true);
    setRoutes([]);
    setSelectedRouteIndex(0);
    setHighlightedSegment(undefined);

    try {
      console.log('[navigate] mode:', mode, 'payload:', payload);

      if (mode === 'on-demand') {
        const response = await apiService.planOnDemand(payload);
        console.log('[navigate] response:', response);
        setItineraryBestId(null);
        setItineraries(response.itineraries ?? []);
        setItineraryMode('On-Demand');
        setItineraryDrawerOpen(true);
      } else if (mode === 'bus') {
        const response = await apiService.planFixedLine({
          ...payload,
          depart_at_min: 480,
          service_date: '20251001',
          transfer_limit: 5,
          max_walk_meters: 2000,
          max_wait_minutes: 60,
          max_invehicle_minutes: 180,
          max_total_minutes: 240
        });
        console.log('[navigate] response:', response);
        setItineraryBestId(response.best_itinerary ?? null);
        const ordered = orderItineraries(response.itineraries ?? [], response.best_itinerary);
        setItineraries(ordered);
        logItineraryGeometries('fixed-line', ordered);
        setItineraryMode('Fixed Line');
        setItineraryDrawerOpen(true);
      } else if (mode === 'car+bus') {
        const response = await apiService.planMultimodal({
          ...payload,
          depart_at_min: 480,
          service_date: '20251001',
          transfer_limit: 5,
          max_walk_meters: 2000,
          max_wait_minutes: 60,
          max_invehicle_minutes: 180,
          max_total_minutes: 240,
          force_taxi: true
        });
        console.log('[navigate] response:', response);
        setItineraryBestId(response.best_itinerary ?? null);
        const ordered = orderItineraries(response.itineraries ?? [], response.best_itinerary);
        setItineraries(ordered);
        logItineraryGeometries('multimodal', ordered);
        setItineraryMode('Multimodal');
        setItineraryDrawerOpen(true);
      } else {
        const response = await apiService.planPrivateVehicle(payload);
        console.log('[navigate] response:', response);
        setItineraryBestId(response.best_itinerary ?? null);
        const ordered = orderItineraries(response.itineraries ?? [], response.best_itinerary);
        setItineraries(ordered);
        logItineraryGeometries('private-vehicle', ordered);
        setItineraryMode('Private Vehicle');
        setItineraryDrawerOpen(true);
      }
    } catch (error) {
      console.error('Navigation error:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleRouteClick = (route: Route) => {
    const index = routes.indexOf(route);
    setSelectedRouteIndex(index);
    setHighlightedSegment(undefined);
  };

  const handleSegmentClick = (coordinates: [number, number][]) => {
    setHighlightedSegment(coordinates);
  };

  const handleMapClick = useCallback((coordinates: [number, number]) => {
    if (depotWizardOpen && depotWizardStep === 'select-zone') {
      try {
        const resolution = Number((import.meta.env.VITE_DEMAND_HEX_RES as string | undefined) ?? 7);
        const hexId = (h3 as any).latLngToCell
          ? (h3 as any).latLngToCell(coordinates[0], coordinates[1], resolution)
          : (h3 as any).geoToH3(coordinates[0], coordinates[1], resolution);
        if (hexId) {
          if (depotHexes.includes(hexId)) {
            setDepotZoneError('That zone is already assigned to another depot.');
            window.alert('You cannot select a zone twice.');
            setContextMenu(null);
            return;
          }
          toggleDepotHex(hexId);
        }
      } catch (error) {
        console.warn('[hex] map click failed', error);
      }
      setContextMenu(null);
      return;
    }

    if (depotWizardOpen && depotWizardStep === 'pick-location') {
      const fallbackName = formatCoordinates(coordinates);
      setDraftDepotLocation({ coords: coordinates, address: fallbackName });
      try {
        const resolution = Number((import.meta.env.VITE_DEMAND_HEX_RES as string | undefined) ?? 7);
        const hexId = (h3 as any).latLngToCell
          ? (h3 as any).latLngToCell(coordinates[0], coordinates[1], resolution)
          : (h3 as any).geoToH3(coordinates[0], coordinates[1], resolution);
        if (hexId) {
          setWizardPinnedHex(hexId);
          setDraftDepotHexes([hexId]);
        }
      } catch (error) {
        console.warn('[hex] failed to pin initial hex', error);
      }
      setDepotGeocoding(true);
      apiService
        .reverseGeocode({ coordinates: [coordinates[0], coordinates[1]] })
        .then((res) => {
          const address = res.address || res.name || fallbackName;
          setDraftDepotLocation({ coords: coordinates, address: truncateAddress(address) });
        })
        .catch(() => {})
        .finally(() => setDepotGeocoding(false));
      setContextMenu(null);
      return;
    }
    // Close context menu when clicking
    setContextMenu(null);
  }, [depotWizardOpen, depotWizardStep, formatCoordinates, truncateAddress, toggleDepotHex]);

  const handleMapRightClick = useCallback((coordinates: [number, number], x: number, y: number) => {
    setContextMenu({ x, y, coordinates });
  }, []);

  const handleSetOrigin = async () => {
    if (!contextMenu?.coordinates) return;
    if (viewMode === 'operator') {
      if (typeof window !== 'undefined' && (window as any).handleOperatorSetOrigin) {
        (window as any).handleOperatorSetOrigin(contextMenu.coordinates);
      }
      return;
    }
    const coords = contextMenu.coordinates;
    const fallbackName = formatCoordinates(coords);
    const location: AutocompleteResult = {
      id: `map-origin-${Date.now()}`,
      name: fallbackName,
      coordinates: coords
    };
    setOrigin(location);
    apiService
      .reverseGeocode({ coordinates: [coords[0], coords[1]] })
      .then((res) => {
        const address = res.address || res.name || fallbackName;
        setOrigin({ ...location, name: truncateAddress(address) });
      })
      .catch(() => {});
  };

  const handleSetDestination = async () => {
    if (!contextMenu?.coordinates) return;
    if (viewMode === 'operator') {
      if (typeof window !== 'undefined' && (window as any).handleOperatorSetDestination) {
        (window as any).handleOperatorSetDestination(contextMenu.coordinates);
      }
      return;
    }
    const coords = contextMenu.coordinates;
    const fallbackName = formatCoordinates(coords);
    const location: AutocompleteResult = {
      id: `map-dest-${Date.now()}`,
      name: fallbackName,
      coordinates: coords
    };
    setDestination(location);
    apiService
      .reverseGeocode({ coordinates: [coords[0], coords[1]] })
      .then((res) => {
        const address = res.address || res.name || fallbackName;
        setDestination({ ...location, name: truncateAddress(address) });
      })
      .catch(() => {});
  };

  const handleRemoveDepot = (id: string) => {
    setDepots(depots.filter(d => d.id !== id));
    if (selectedDepotId === id) {
      setSelectedDepotId(null);
    }
  };

  const handleGtfsUploaded = useCallback((payload: { gtfs_id: string; gtfs_name: string; job_id: string; status: string }) => {
    setGtfsUploads((prev) => [payload, ...prev]);
  }, []);

  useEffect(() => {
    const pendingJobs = gtfsUploads.filter((upload) => upload.status === 'pending' || upload.status === 'processing');
    if (pendingJobs.length === 0) return;

    const interval = window.setInterval(async () => {
      try {
        const updates = await Promise.all(
          pendingJobs.map(async (upload) => {
            console.log('[gtfs] polling', upload.job_id);
            const response = await fetch(buildUrl(`/gtfs/jobs/${upload.job_id}`));
            if (!response.ok) {
              return upload;
            }
            const payload = await response.json();
            console.log('[gtfs] status', upload.job_id, payload.status);
            return {
              ...upload,
              status: payload.status ?? upload.status
            };
          })
        );

        setGtfsUploads((prev) =>
          prev.map((upload) => {
            const update = updates.find((item) => item.job_id === upload.job_id);
            return update ?? upload;
          })
        );
      } catch (error) {
        console.error('[api] gtfs polling error:', error);
      }
    }, 2000);

    return () => window.clearInterval(interval);
  }, [gtfsUploads]);

  useEffect(() => {
    if (viewMode !== 'operator') return;

    let cancelled = false;

    const loadLists = async () => {
      try {
        const [depotsResponse, gtfsResponse] = await Promise.all([
          apiService.listOnDemandDepots(),
          apiService.listGtfsFeeds()
        ]);

        if (!cancelled) {
          setDepots((prev) => {
            const existingIds = new Set(prev.map((depot) => depot.id));
            const incoming = depotsResponse
              .filter((item) => !existingIds.has(item.depot_id))
              .map((item) => {
                const vehicleCount = item.vehicles?.length ?? 0;
                const capacity =
                  item.vehicles && item.vehicles.length > 0
                    ? item.vehicles[0]?.capacity ?? 0
                    : 0;
                return {
                  id: item.depot_id,
                  coordinates: [item.lat, item.lon] as [number, number],
                  vehicles: vehicleCount,
                  capacity,
                  address: item.name,
                  serviceZoneHexes: item.h3_ids ?? []
                };
              });
            return [...prev, ...incoming];
          });

          setGtfsUploads((prev) => {
            const existingIds = new Set(prev.map((item) => item.gtfs_id));
            const incoming = gtfsResponse
              .filter((item) => !existingIds.has(item.gtfs_id))
              .map((item) => ({
                gtfs_id: item.gtfs_id,
                gtfs_name: item.gtfs_name,
                job_id: `gtfs-${item.gtfs_id}`,
                status: 'available'
              }));
            return [...prev, ...incoming];
          });
        }
      } catch (error) {
        console.error('[api] list operator data error:', error);
      }
    };

    loadLists();

    return () => {
      cancelled = true;
    };
  }, [viewMode]);

  const handleSaveDepot = useCallback(async () => {
    if (!draftDepotLocation) return;
    const resolution = draftDepotHexes[0]
      ? ((h3 as any).getResolution
        ? (h3 as any).getResolution(draftDepotHexes[0])
        : (h3 as any).h3GetResolution?.(draftDepotHexes[0]))
      : undefined;
    try {
      const response = await apiService.createDepot({
        coordinates: draftDepotLocation.coords,
        address: draftDepotLocation.address,
        vehicles: draftDepotVehicles,
        capacity: draftDepotCapacity,
        service_zone_hex_ids: draftDepotHexes,
        h3_resolution: typeof resolution === 'number' ? resolution : undefined
      });
      console.log('[api] createDepot response:', response);
      const depot: Depot = {
        id: response.depot_id ?? `depot-${Date.now()}`,
        coordinates: [response.lat, response.lon],
        vehicles: response.vehicle_count ?? draftDepotVehicles,
        capacity: response.capacity ?? draftDepotCapacity,
        address: response.address ?? draftDepotLocation.address,
        serviceZoneHexes: draftDepotHexes
      };
      setDepots((prev) => [...prev, depot]);
      setSelectedDepotId(depot.id);
      closeDepotWizard();
      setShowDepotHexes(false);
    } catch (error) {
      console.error('[api] createDepot error:', error);
    }
  }, [
    draftDepotLocation,
    draftDepotVehicles,
    draftDepotCapacity,
    draftDepotHexes,
    closeDepotWizard
  ]);

  const handleBusRouteUpdate = (routes: BusRoute[]) => {
    setBusRoutes(routes);
  };

  const handleEvaluate = async () => {
    setEvaluating(true);
    try {
      const result = await apiService.evaluate({
        modes: [
          {
            type: 'on-demand',
            config: { depots }
          }
        ]
      });
      setEvaluationResult(result);
      setShowEvaluationDrawer(true);
      
      // Initialize legend items
      setLegendItems([
        { id: 'coverage', label: 'Coverage Area', color: '#10b981', visible: true },
        { id: 'heatmap', label: 'Demand Heatmap', color: '#ef4444', visible: true },
        { id: 'boundary', label: 'Service Boundaries', color: '#3b82f6', visible: true }
      ]);
    } catch (error) {
      console.error('Evaluation error:', error);
    } finally {
      setEvaluating(false);
    }
  };

  const handleLegendToggle = (id: string) => {
    setLegendItems(items =>
      items.map(item =>
        item.id === id ? { ...item, visible: !item.visible } : item
      )
    );
  };

  const handleViewModeChange = (mode: ViewMode) => {
    setViewMode(mode);
  };

  const handleResetPassenger = () => {
    setOrigin(null);
    setDestination(null);
    setRoutes([]);
    setSelectedRouteIndex(0);
    setHighlightedSegment(undefined);
  };

  const handleResetOperator = () => {
    setDepots([]);
    setBusRoutes([]);
    setEvaluationResult(null);
    setShowEvaluationDrawer(false);
    setLegendItems([]);
    closeDepotWizard();
  };


  const MapLoadingOverlay = () => (
    <div className="absolute inset-0 z-[1000] flex items-center justify-center bg-white/70 backdrop-blur-sm">
      <div className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white/90 px-4 py-3 shadow-lg">
        <span className="inline-flex h-5 w-5 animate-spin rounded-full border-2 border-slate-300 border-t-blue-600" />
        <span className="text-sm font-medium text-slate-700">{loadingLabel}</span>
      </div>
    </div>
  );

  return (
    <div className="h-screen flex flex-col">
      {/* Top Bar */}
      <div className="h-16 bg-white border-b flex items-center justify-between px-6">
        <h1 className="text-2xl">Transit Planner</h1>
        <div className="flex gap-3">
          <div className="flex gap-2">
            <button
              onClick={() => setBaseMapStyle('standard')}
              className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                baseMapStyle === 'standard'
                  ? 'bg-slate-900 text-white'
                  : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
              }`}
            >
              Standard Map
            </button>
            <button
              onClick={() => setBaseMapStyle('light')}
              className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                baseMapStyle === 'light'
                  ? 'bg-slate-900 text-white'
                  : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
              }`}
            >
              Light (No Labels)
            </button>
          </div>
          <button
            onClick={() => handleViewModeChange('passenger')}
            className={`px-6 py-2 rounded-lg font-medium transition-colors ${
              viewMode === 'passenger'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
            }`}
          >
            Passenger View
          </button>
          <button
            onClick={() => handleViewModeChange('operator')}
            className={`px-6 py-2 rounded-lg font-medium transition-colors ${
              viewMode === 'operator'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
            }`}
          >
            Operator View
          </button>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex min-h-0 overflow-hidden relative">
        {/* Sidebar */}
        {viewMode === 'passenger' ? (
          <PassengerView
            origin={origin}
            destination={destination}
            onOriginChange={setOrigin}
            onDestinationChange={setDestination}
            onNavigate={handleNavigate}
            routes={routes}
            loading={loading}
            onRouteClick={handleRouteClick}
            onSegmentClick={handleSegmentClick}
            onReset={handleResetPassenger}
          />
        ) : (
          <OperatorView
            onRemoveDepot={handleRemoveDepot}
            depots={depots}
            onBusRouteUpdate={handleBusRouteUpdate}
            onEvaluate={handleEvaluate}
            onReset={handleResetOperator}
            onStartDepotWizard={startDepotWizard}
            depotWizardActive={depotWizardOpen}
            onGtfsUploaded={handleGtfsUploaded}
            showDepotHexes={showDepotHexes}
            onToggleDepotHexes={setShowDepotHexes}
            evaluating={evaluating}
          />
        )}

        {/* Map + Itinerary Panel */}
        {viewMode === 'passenger' ? (
          <div className="flex flex-1 min-h-0 min-w-0">
            <div className="relative flex-1 min-h-0 min-w-0">
              <MapView
                markers={markers}
                routes={routePolylines}
                onMapClick={handleMapClick}
                onMapRightClick={handleMapRightClick}
                highlightedSegment={highlightedSegment}
                layers={mapLayers}
                baseMapStyle={baseMapStyle}
                showHexGrid={viewMode === 'operator' && depotWizardOpen && depotWizardStep === 'select-zone'}
                selectedHexes={draftDepotHexes}
                onHexClick={depotWizardOpen && depotWizardStep === 'select-zone' ? toggleDepotHex : undefined}
              />
              {mapLoading && <MapLoadingOverlay />}
            </div>
            {(itineraryDrawerOpen || itineraries.length > 0) && (
              <div
                className="h-full shrink-0 border-l bg-white shadow-xl"
                style={{ width: '30vw', maxWidth: '30vw', minWidth: '30vw' }}
              >
                <ItineraryDrawer
                  open
                  onOpenChange={setItineraryDrawerOpen}
                  itineraries={itineraries}
                  bestItineraryId={itineraryBestId}
                  selectedItineraryId={selectedItineraryId}
                  onSelectItinerary={(itinerary) => {
                    setSelectedItineraryId(itinerary?.itinerary_id ?? null);
                  }}
                  onSelectLeg={(leg) => {
                    if (typeof (leg as any)?.geometry === 'string' && (leg as any).geometry.length > 0) {
                      setHighlightedSegment(decodePolyline((leg as any).geometry));
                    } else {
                      setHighlightedSegment(undefined);
                    }
                  }}
                  modeLabel={itineraryMode}
                />
              </div>
            )}
          </div>
        ) : (
          <div className="flex flex-1 min-h-0 min-w-0">
            <div className="relative flex-1 min-h-0 min-w-0 flex flex-col">
              <div className="relative flex-1 min-h-0 min-w-0">
                <MapView
                  markers={markers}
                  routes={routePolylines}
                  onMapClick={handleMapClick}
                  onMapRightClick={handleMapRightClick}
                  highlightedSegment={highlightedSegment}
                  layers={mapLayers}
                  baseMapStyle={baseMapStyle}
                  showHexGrid={viewMode === 'operator' && (depotWizardOpen || depots.length > 0)}
                  hexDisplayMode={
                    depotWizardOpen && depotWizardStep === 'select-zone'
                      ? 'grid'
                      : showDepotHexes
                      ? 'grid'
                      : 'established-only'
                  }
                  selectedHexes={depotWizardOpen ? draftDepotHexes : []}
                  establishedHexes={depotHexes}
                  activeHexes={activeDepotHexes}
                  allowMapPan={!(depotWizardOpen && depotWizardStep === 'select-zone')}
                />
                {mapLoading && <MapLoadingOverlay />}
                <div className="absolute inset-0 z-10 pointer-events-none">
                {/* Map Legend */}
                {viewMode === 'operator' && evaluationResult && (
                  <div className="pointer-events-auto">
                    <MapLegend items={legendItems} onToggle={handleLegendToggle} />
                  </div>
                )}

                {/* Evaluation Drawer */}
                {viewMode === 'operator' && (
                  <div className="pointer-events-auto">
                    <EvaluationDrawer
                      isOpen={showEvaluationDrawer}
                      onClose={() => setShowEvaluationDrawer(false)}
                      metrics={evaluationResult?.metrics || null}
                    />
                  </div>
                )}
                </div>
              </div>
              {depotWizardOpen && (
                <div className="shrink-0 border-t border-slate-200 bg-white shadow-[0_-10px_30px_rgba(0,0,0,0.08)]">
                  <div className="mx-auto w-full max-w-[900px]">
                    <div className="border-b px-4 py-3">
                      <div className="text-sm font-semibold text-slate-800">Add Depot</div>
                      <div className="text-xs text-slate-500">
                        {depotWizardStep === 'pick-location' && 'Step 1 of 3: Pick location'}
                        {depotWizardStep === 'select-zone' && 'Step 2 of 3: Select service zone'}
                        {depotWizardStep === 'vehicles' && 'Step 3 of 3: Vehicles & capacity'}
                      </div>
                    </div>

                    {depotWizardStep === 'pick-location' && (
                      <div className="px-4 py-4 space-y-3">
                        <div className="text-sm text-slate-700">
                          Pick a spot on the map to place the depot.
                        </div>
                        <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
                          {draftDepotLocation
                            ? `${draftDepotLocation.address ?? formatCoordinates(draftDepotLocation.coords)}`
                            : 'No location selected yet.'}
                          {depotGeocoding && <span className="ml-2 text-slate-400">Looking up address...</span>}
                        </div>
                      </div>
                    )}

                    {depotWizardStep === 'select-zone' && (
                      <div className="px-4 py-4 space-y-3">
                        <div className="text-sm text-slate-700">
                          Select contiguous hexagons for the service zone.
                        </div>
                        <div className="text-xs text-slate-600">
                          Selected hexes: <span className="font-semibold text-slate-800">{draftDepotHexes.length}</span>
                        </div>
                        {depotZoneError && (
                          <div className="text-xs text-red-600">{depotZoneError}</div>
                        )}
                      </div>
                    )}

                    {depotWizardStep === 'vehicles' && (
                      <div className="px-4 py-4 space-y-4">
                        <div className="text-sm text-slate-700">
                          Set a homogeneous fleet size and capacity for this depot.
                        </div>
                        <div className="space-y-3">
                          <div>
                            <label className="block text-xs text-slate-600 mb-1">Vehicles</label>
                            <input
                              type="number"
                              min={1}
                              value={draftDepotVehicles}
                              onChange={(e) => setDraftDepotVehicles(parseInt(e.target.value) || 0)}
                              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                            />
                          </div>
                          <div>
                            <label className="block text-xs text-slate-600 mb-1">Vehicle Capacity</label>
                            <input
                              type="number"
                              min={1}
                              value={draftDepotCapacity}
                              onChange={(e) => setDraftDepotCapacity(parseInt(e.target.value) || 0)}
                              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                            />
                          </div>
                        </div>
                      </div>
                    )}

                    <div className="border-t px-4 py-3 flex items-center justify-between">
                      <button
                        onClick={closeDepotWizard}
                        className="text-sm text-slate-600 hover:text-slate-800"
                      >
                        Cancel
                      </button>
                      <div className="flex gap-2">
                        {depotWizardStep !== 'pick-location' && (
                          <button
                            onClick={() => {
                              if (depotWizardStep === 'select-zone') {
                                setDepotWizardStep('pick-location');
                              } else {
                                setDepotWizardStep('select-zone');
                              }
                            }}
                            className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50"
                          >
                            Back
                          </button>
                        )}
                        {depotWizardStep === 'pick-location' && (
                          <button
                            onClick={() => setDepotWizardStep('select-zone')}
                            disabled={!draftDepotLocation}
                            className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm text-white hover:bg-blue-700 disabled:bg-slate-300 disabled:cursor-not-allowed"
                          >
                            Next
                          </button>
                        )}
                        {depotWizardStep === 'select-zone' && (
                          <button
                            onClick={() => {
                              if (draftDepotHexes.length === 0) {
                                setDepotZoneError('Select at least one hexagon.');
                                return;
                              }
                              if (!isHexSelectionContiguous(draftDepotHexes)) {
                                setDepotZoneError('Selection must be contiguous (touching sides only).');
                                return;
                              }
                              setDepotZoneError(null);
                              setDepotWizardStep('vehicles');
                            }}
                            className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm text-white hover:bg-blue-700"
                          >
                            Done
                          </button>
                        )}
                        {depotWizardStep === 'vehicles' && (
                          <button
                            onClick={handleSaveDepot}
                            className="rounded-lg bg-green-600 px-3 py-1.5 text-sm text-white hover:bg-green-700"
                          >
                            Save Depot
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
            {(depots.length > 0 || gtfsUploads.length > 0) && (
              <div
                className="h-full shrink-0 border-l bg-white shadow-xl flex flex-col"
                style={{
                  width: '26vw',
                  maxWidth: '26vw',
                  minWidth: '26vw',
                  paddingBottom: depotWizardOpen ? '220px' : undefined
                }}
              >
                <div className="h-full flex flex-col overflow-y-auto">
                  <div className="px-4 py-3 border-b text-sm font-semibold text-slate-700">Depots</div>
                  <div className="p-4 space-y-3">
                    {depots.map((depot, index) => (
                      <button
                        key={depot.id}
                        type="button"
                        onClick={() =>
                          setSelectedDepotId((prev) => (prev === depot.id ? null : depot.id))
                        }
                        className={`w-full text-left rounded-lg border p-3 transition-colors ${
                          selectedDepotId === depot.id
                            ? 'border-blue-500 bg-blue-50'
                            : 'border-slate-200 hover:border-slate-300'
                        }`}
                      >
                        <div className="text-sm font-semibold text-slate-800">
                          Depot {index + 1}
                        </div>
                        <div className="text-xs text-slate-500 mt-1">
                          {depot.address ?? formatCoordinates(depot.coordinates)}
                        </div>
                        <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-slate-600">
                          <div>
                            <span className="font-medium text-slate-700">Vehicles:</span> {depot.vehicles}
                          </div>
                          <div>
                            <span className="font-medium text-slate-700">Capacity:</span> {depot.capacity}
                          </div>
                          <div className="col-span-2">
                            <span className="font-medium text-slate-700">Service Hexes:</span>{' '}
                            {depot.serviceZoneHexes?.length ?? 0}
                          </div>
                        </div>
                      </button>
                    ))}
                  </div>
                {gtfsUploads.length > 0 && (
                  <div className="border-t border-slate-200">
                    <div className="px-4 py-3 text-sm font-semibold text-slate-700">GTFS</div>
                    <div className="px-4 pb-4 space-y-2">
                      {gtfsUploads.map((upload) => (
                        <button
                          key={upload.gtfs_id}
                          type="button"
                          onClick={async () => {
                            if (gtfsPreview?.gtfs_id === upload.gtfs_id) {
                              setGtfsPreview(null);
                              return;
                            }
                            setGtfsPreviewLoadingId(upload.gtfs_id);
                            try {
                              const response = await fetch(buildUrl(`/gtfs/${upload.gtfs_id}/preview?limit=15`));
                              if (!response.ok) {
                                throw new Error(await response.text());
                              }
                              const payload = await response.json();
                              const shapePoints = payload?.shape_points ?? [];
                              const stops = payload?.stops ?? [];
                              const routes = payload?.routes ?? [];
                              const uniqueShapeIds = Array.from(
                                new Set(shapePoints.map((point: any) => point.shape_id))
                              );
                              console.log('[gtfs] preview summary', {
                                gtfs_id: payload?.gtfs_id,
                                stops_count: stops.length,
                                shape_points_count: shapePoints.length,
                                routes_count: routes.length,
                                shape_ids_count: uniqueShapeIds.length
                              });
                              console.log('[gtfs] preview keys', {
                                payload: payload ? Object.keys(payload) : [],
                                first_stop_keys: stops[0] ? Object.keys(stops[0]) : [],
                                first_shape_point_keys: shapePoints[0] ? Object.keys(shapePoints[0]) : [],
                                first_route_keys: routes[0] ? Object.keys(routes[0]) : []
                              });
                              console.log('[gtfs] preview samples', {
                                first_stop: stops[0] ?? null,
                                first_shape_point: shapePoints[0] ?? null,
                                first_route: routes[0] ?? null,
                                first_shape_id: uniqueShapeIds[0] ?? null,
                                last_shape_id: uniqueShapeIds[uniqueShapeIds.length - 1] ?? null
                              });
                              setGtfsPreview(payload);
                            } catch (error) {
                              console.error('[api] gtfs preview error:', error);
                            } finally {
                              setGtfsPreviewLoadingId(null);
                            }
                          }}
                          className={`w-full text-left rounded-lg border p-3 text-xs transition-colors ${
                            gtfsPreview?.gtfs_id === upload.gtfs_id
                              ? 'border-orange-400 bg-orange-50'
                              : 'border-slate-200 hover:border-slate-300'
                          }`}
                        >
                          <div className="font-semibold text-slate-800">{upload.gtfs_name}</div>
                          <div className="mt-1">GTFS ID: {upload.gtfs_id}</div>
                          <div className="mt-1">Status: {upload.status}</div>
                          {gtfsPreviewLoadingId === upload.gtfs_id && (
                            <div className="mt-2 text-xs text-slate-500">Loading preview…</div>
                          )}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
                {depotWizardOpen && (
                  <div className="border-t border-slate-200 bg-slate-50 px-4 py-3 text-xs text-slate-600">
                    Wizard active — drawer pinned above.
                  </div>
                )}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Global Context Menu */}
      {contextMenu && (
        <MapContextMenu
          x={contextMenu.x}
          y={contextMenu.y}
          onSetOrigin={handleSetOrigin}
          onSetDestination={handleSetDestination}
          onClose={() => setContextMenu(null)}
        />
      )}
    </div>
  );
}
