import { useState, useCallback, useMemo } from 'react';
import { MapView, Marker, RoutePolyline, MapLayer } from './components/MapView';
import { PassengerView } from './components/PassengerView';
import { OperatorView, Depot, BusRoute } from './components/OperatorView';
import { EvaluationDrawer } from './components/EvaluationDrawer';
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
    return polylines;
  }, [viewMode, routes, selectedRouteIndex, busRoutes]);

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

  const handleNavigate = async (modes: string[]) => {
    if (!origin || !destination) return;

    setLoading(true);
    setRoutes([]);
    setSelectedRouteIndex(0);
    setHighlightedSegment(undefined);

    try {
      const response = await apiService.navigate({
        origin: origin.coordinates,
        destination: destination.coordinates,
        modes
      });
      setRoutes(response.routes);
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
    if (viewMode === 'passenger') {
      setContextMenu({ x, y, coordinates });
    }
  }, [viewMode]);

  const handleSetOrigin = async () => {
    if (contextMenu) {
      try {
        const result = await apiService.reverseGeocode({ coordinates: contextMenu.coordinates });
        const location: AutocompleteResult = {
          id: `map-origin-${Date.now()}`,
          name: result.name,
          coordinates: contextMenu.coordinates
        };
        setOrigin(location);
      } catch (error) {
        console.error('Failed to set origin:', error);
      }
    }
  };

  const handleSetDestination = async () => {
    if (contextMenu) {
      try {
        const result = await apiService.reverseGeocode({ coordinates: contextMenu.coordinates });
        const location: AutocompleteResult = {
          id: `map-dest-${Date.now()}`,
          name: result.name,
          coordinates: contextMenu.coordinates
        };
        setDestination(location);
      } catch (error) {
        console.error('Failed to set destination:', error);
      }
    }
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
      <div className="flex-1 flex overflow-hidden relative">
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

        {/* Map */}
        <div className="flex-1 relative">
          <MapView
            markers={markers}
            routes={routePolylines}
            onMapClick={handleMapClick}
            onMapRightClick={handleMapRightClick}
            highlightedSegment={highlightedSegment}
            layers={mapLayers}
          />
          
          {/* Map Legend */}
          {viewMode === 'operator' && evaluationResult && (
            <MapLegend items={legendItems} onToggle={handleLegendToggle} />
          )}

          {/* Context Menu */}
          {contextMenu && (
            <MapContextMenu
              x={contextMenu.x}
              y={contextMenu.y}
              onSetOrigin={handleSetOrigin}
              onSetDestination={handleSetDestination}
              onClose={() => setContextMenu(null)}
            />
          )}

          {/* Evaluation Drawer */}
          {viewMode === 'operator' && (
            <EvaluationDrawer
              isOpen={showEvaluationDrawer}
              onClose={() => setShowEvaluationDrawer(false)}
              metrics={evaluationResult?.metrics || null}
            />
          )}
        </div>
      </div>
    </div>
  );
}