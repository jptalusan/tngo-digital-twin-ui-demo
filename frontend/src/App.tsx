import { useState, useCallback, useMemo, useEffect } from 'react';
import { MapView, Marker, RoutePolyline, MapLayer } from './components/MapView';
import { PassengerView } from './components/PassengerView';
import { OperatorView, Depot, BusRoute } from './components/OperatorView';
import { EvaluationDrawer } from './components/EvaluationDrawer';
import { ItineraryDrawer } from './components/ItineraryDrawer';
import { MapLegend, LegendItem } from './components/MapLegend';
import { MapContextMenu } from './components/MapContextMenu';
import { apiService, AutocompleteResult, Route, EvaluationResponse } from './services/api';

type ViewMode = 'passenger' | 'operator';

export default function App() {
  const [viewMode, setViewMode] = useState<ViewMode>('passenger');
  const [origin, setOrigin] = useState<AutocompleteResult | null>(null);
  const [destination, setDestination] = useState<AutocompleteResult | null>(null);
  const [routes, setRoutes] = useState<Route[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedRouteIndex, setSelectedRouteIndex] = useState<number>(0);
  const [highlightedSegment, setHighlightedSegment] = useState<[number, number][] | undefined>();
  const [depots, setDepots] = useState<Depot[]>([]);
  const [mapClickEnabled, setMapClickEnabled] = useState(false);
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
    }
    return m;
  }, [viewMode, origin, destination, depots]);

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
    return polylines;
  }, [
    viewMode,
    routes,
    selectedRouteIndex,
    busRoutes,
    itineraries,
    selectedItineraryId,
    selectedItinerary,
    extractItineraryGeometry
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
    if (mapClickEnabled && typeof window !== 'undefined' && (window as any).handleOperatorMapClick) {
      (window as any).handleOperatorMapClick(coordinates);
    }
    // Close context menu when clicking
    setContextMenu(null);
  }, [mapClickEnabled]);

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

  const handleAddDepot = (depot: Depot) => {
    setDepots([...depots, depot]);
  };

  const handleRemoveDepot = (id: string) => {
    setDepots(depots.filter(d => d.id !== id));
  };

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
    setMapClickEnabled(false);
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
            onAddDepot={handleAddDepot}
            onRemoveDepot={handleRemoveDepot}
            depots={depots}
            onMapClickEnabled={setMapClickEnabled}
            onBusRouteUpdate={handleBusRouteUpdate}
            onEvaluate={handleEvaluate}
            onReset={handleResetOperator}
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
          <div className="relative flex-1 min-h-0">
            <MapView
              markers={markers}
              routes={routePolylines}
              onMapClick={handleMapClick}
              onMapRightClick={handleMapRightClick}
              highlightedSegment={highlightedSegment}
              layers={mapLayers}
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
