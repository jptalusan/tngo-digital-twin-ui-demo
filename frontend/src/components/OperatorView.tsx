import { useState } from 'react';
import { Car, Bus, Plus, Trash2, Upload, PlayCircle, ChevronDown, ChevronUp, ChevronLeft, ChevronRight, RotateCcw } from 'lucide-react';
import { apiService } from '../services/api';

export interface Depot {
  id: string;
  coordinates: [number, number];
  vehicles: number;
  capacity: number;
}

export interface BusRoute {
  id: string;
  origin: string;
  destination: string;
  buses: number;
  capacity: number;
  frequency: number;
  roundTrip: boolean;
  geometry?: [number, number][];
}

interface OperatorViewProps {
  onAddDepot: (depot: Depot) => void;
  onRemoveDepot: (id: string) => void;
  depots: Depot[];
  onMapClickEnabled: (enabled: boolean) => void;
  onBusRouteUpdate: (routes: BusRoute[]) => void;
  onEvaluate: () => void;
  onReset: () => void;
  evaluating?: boolean;
}

export function OperatorView({ 
  onAddDepot, 
  onRemoveDepot, 
  depots, 
  onMapClickEnabled,
  onBusRouteUpdate,
  onEvaluate,
  onReset,
  evaluating = false
}: OperatorViewProps) {
  const [selectedModes, setSelectedModes] = useState<Set<string>>(new Set());
  const [addingDepot, setAddingDepot] = useState(false);
  const [newDepotVehicles, setNewDepotVehicles] = useState(5);
  const [newDepotCapacity, setNewDepotCapacity] = useState(4);
  const [busRoutes, setBusRoutes] = useState<BusRoute[]>([]);
  const [activeBusRouteId, setActiveBusRouteId] = useState<string | null>(null);
  const [gtfsMode, setGtfsMode] = useState(false);
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [onDemandExpanded, setOnDemandExpanded] = useState(true);
  const [busExpanded, setBusExpanded] = useState(true);

  const toggleMode = (mode: string) => {
    const newModes = new Set(selectedModes);
    if (newModes.has(mode)) {
      newModes.delete(mode);
    } else {
      newModes.add(mode);
    }
    setSelectedModes(newModes);
  };

  const handleAddDepotClick = () => {
    setAddingDepot(true);
    onMapClickEnabled(true);
  };

  const handleAddDepot = (coordinates: [number, number]) => {
    if (addingDepot) {
      const depot: Depot = {
        id: `depot-${Date.now()}`,
        coordinates,
        vehicles: newDepotVehicles,
        capacity: newDepotCapacity
      };
      onAddDepot(depot);
      setAddingDepot(false);
      onMapClickEnabled(false);
    }
  };

  const handleCancelAddDepot = () => {
    setAddingDepot(false);
    onMapClickEnabled(false);
  };

  const addBusRoute = () => {
    const newRoute: BusRoute = {
      id: `route-${Date.now()}`,
      origin: '',
      destination: '',
      buses: 3,
      capacity: 40,
      frequency: 15,
      roundTrip: true
    };
    const updatedRoutes = [...busRoutes, newRoute];
    setBusRoutes(updatedRoutes);
    setActiveBusRouteId(newRoute.id);
    onBusRouteUpdate(updatedRoutes);
  };

  const updateBusRoute = async (id: string, updates: Partial<BusRoute>) => {
    const updatedRoutes = busRoutes.map(route => 
      route.id === id ? { ...route, ...updates } : route
    );
    setBusRoutes(updatedRoutes);
    onBusRouteUpdate(updatedRoutes);

    // If origin and destination are both set, fetch geometry
    const updatedRoute = updatedRoutes.find(r => r.id === id);
    if (updatedRoute && updatedRoute.origin && updatedRoute.destination) {
      try {
        const geometry = await apiService.getBusRouteGeometry({
          origin: updatedRoute.origin,
          destination: updatedRoute.destination
        });
        const routesWithGeometry = updatedRoutes.map(route =>
          route.id === id ? { ...route, geometry: geometry.geometry } : route
        );
        setBusRoutes(routesWithGeometry);
        onBusRouteUpdate(routesWithGeometry);
      } catch (error) {
        console.error('Error fetching route geometry:', error);
      }
    }
  };

  const removeBusRoute = (id: string) => {
    const updatedRoutes = busRoutes.filter(route => route.id !== id);
    setBusRoutes(updatedRoutes);
    if (activeBusRouteId === id) {
      setActiveBusRouteId(updatedRoutes.length > 0 ? updatedRoutes[updatedRoutes.length - 1].id : null);
    }
    onBusRouteUpdate(updatedRoutes);
  };

  const formatCoordinates = (coordinates: [number, number]) =>
    `${coordinates[0].toFixed(5)}, ${coordinates[1].toFixed(5)}`;

  const setRouteEndpoint = (type: 'origin' | 'destination', coordinates: [number, number]) => {
    if (busRoutes.length === 0) return;
    const targetRouteId = activeBusRouteId ?? busRoutes[busRoutes.length - 1].id;
    const value = formatCoordinates(coordinates);
    void updateBusRoute(targetRouteId, { [type]: value });
  };

  // Expose handleAddDepot to parent via window object for map clicks
  if (typeof window !== 'undefined') {
    (window as any).handleOperatorMapClick = handleAddDepot;
    (window as any).handleOperatorSetOrigin = (coordinates: [number, number]) =>
      setRouteEndpoint('origin', coordinates);
    (window as any).handleOperatorSetDestination = (coordinates: [number, number]) =>
      setRouteEndpoint('destination', coordinates);
  }

  return (
    <div className={`${isCollapsed ? 'w-16' : 'w-96'} h-full bg-white border-r transition-all duration-300 relative flex flex-col`}>
      {/* Collapse Button */}
      <div className={`flex items-center ${isCollapsed ? 'justify-center py-4' : 'justify-between p-4'} border-b`}>
        {!isCollapsed && <h2 className="text-lg font-semibold truncate">Operator Config</h2>}
        <button
          onClick={() => setIsCollapsed(!isCollapsed)}
          className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          title={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {isCollapsed ? <ChevronRight size={20} /> : <ChevronLeft size={20} />}
        </button>
      </div>

      {/* Collapsed State - Clickable Tab */}
      {isCollapsed && (
        <div 
          onClick={() => setIsCollapsed(false)}
          className="flex-1 w-full hover:bg-gray-50 cursor-pointer flex items-center justify-center"
        >
          <div className="transform -rotate-90 text-sm font-medium text-gray-600 whitespace-nowrap">
            Operator
          </div>
        </div>
      )}

      {/* Main Content */}
      {!isCollapsed && (
        <>
          <div className="p-6 w-full flex-1 overflow-y-auto">


            {/* Mode Selection */}
            <div className="mb-6">
              <label className="block text-sm mb-3">Service Modes</label>
              <div className="space-y-3">
                <button
                  onClick={() => toggleMode('on-demand')}
                  className={`w-full flex items-center gap-2 px-4 py-3 rounded-lg border-2 transition-colors ${
                    selectedModes.has('on-demand')
                      ? 'border-blue-500 bg-blue-50 text-blue-700'
                      : 'border-gray-300 hover:border-gray-400'
                  }`}
                >
                  <Car size={20} />
                  <span>On-Demand</span>
                </button>

                <button
                  onClick={() => toggleMode('bus')}
                  className={`w-full flex items-center gap-2 px-4 py-3 rounded-lg border-2 transition-colors ${
                    selectedModes.has('bus')
                      ? 'border-blue-500 bg-blue-50 text-blue-700'
                      : 'border-gray-300 hover:border-gray-400'
                  }`}
                >
                  <Bus size={20} />
                  <span>Bus (Fixed Line)</span>
                </button>
              </div>
            </div>

            {/* On-Demand Configuration */}
            {selectedModes.has('on-demand') && (
              <div className="mb-6 border rounded-lg">
                <button
                  onClick={() => setOnDemandExpanded(!onDemandExpanded)}
                  className="w-full px-4 py-3 bg-gray-50 hover:bg-gray-100 flex items-center justify-between transition-colors rounded-t-lg"
                >
                  <h3 className="font-medium">On-Demand Configuration</h3>
                  {onDemandExpanded ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
                </button>
                
                {onDemandExpanded && (
                  <div className="p-4">
                    <div className="mb-4">
                      <label className="block text-sm mb-2">Vehicles per Depot</label>
                      <input
                        type="number"
                        value={newDepotVehicles}
                        onChange={(e) => setNewDepotVehicles(parseInt(e.target.value) || 0)}
                        className="w-full px-3 py-2 border rounded-lg"
                        min="1"
                      />
                    </div>

                    <div className="mb-4">
                      <label className="block text-sm mb-2">Vehicle Capacity</label>
                      <input
                        type="number"
                        value={newDepotCapacity}
                        onChange={(e) => setNewDepotCapacity(parseInt(e.target.value) || 0)}
                        className="w-full px-3 py-2 border rounded-lg"
                        min="1"
                      />
                    </div>

                    {!addingDepot ? (
                      <button
                        onClick={handleAddDepotClick}
                        className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                      >
                        <Plus size={20} />
                        <span>Add Depot (Click Map)</span>
                      </button>
                    ) : (
                      <button
                        onClick={handleCancelAddDepot}
                        className="w-full px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700"
                      >
                        Cancel
                      </button>
                    )}

                    {depots.length > 0 && (
                      <div className="mt-4 space-y-2">
                        <div className="text-sm mb-2">Depots ({depots.length})</div>
                        {depots.map((depot, index) => (
                          <div key={depot.id} className="flex items-center justify-between p-2 bg-gray-50 rounded">
                            <span className="text-sm">
                              Depot {index + 1}: {depot.vehicles} vehicles (cap: {depot.capacity})
                            </span>
                            <button
                              onClick={() => onRemoveDepot(depot.id)}
                              className="text-red-600 hover:text-red-700"
                            >
                              <Trash2 size={16} />
                            </button>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Bus Configuration */}
            {selectedModes.has('bus') && (
              <div className="mb-6 border rounded-lg">
                <button
                  onClick={() => setBusExpanded(!busExpanded)}
                  className="w-full px-4 py-3 bg-gray-50 hover:bg-gray-100 flex items-center justify-between transition-colors rounded-t-lg"
                >
                  <h3 className="font-medium">Fixed Line Configuration</h3>
                  {busExpanded ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
                </button>

                {busExpanded && (
                  <div className="p-4">
                    <div className="mb-4 flex gap-2">
                      <button
                        onClick={() => setGtfsMode(false)}
                        className={`flex-1 px-4 py-2 rounded-lg border-2 ${
                          !gtfsMode ? 'border-blue-500 bg-blue-50' : 'border-gray-300'
                        }`}
                      >
                        Custom Routes
                      </button>
                      <button
                        onClick={() => setGtfsMode(true)}
                        className={`flex-1 px-4 py-2 rounded-lg border-2 ${
                          gtfsMode ? 'border-blue-500 bg-blue-50' : 'border-gray-300'
                        }`}
                      >
                        Upload GTFS
                      </button>
                    </div>

                    {gtfsMode ? (
                      <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center">
                        <Upload size={32} className="mx-auto mb-2 text-gray-400" />
                        <p className="text-sm text-gray-600 mb-3">Upload GTFS File</p>
                        <button className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
                          Choose File
                        </button>
                      </div>
                    ) : (
                      <div>
                        <button
                          onClick={addBusRoute}
                          className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 mb-4"
                        >
                          <Plus size={20} />
                          <span>Add Route</span>
                        </button>

                        <div className="space-y-3">
                          {busRoutes.map((route) => (
                            <div key={route.id} className="border rounded-lg p-3">
                              <div className="flex items-center justify-between mb-3">
                                <span className="text-sm">Route Configuration</span>
                                <button
                                  onClick={() => removeBusRoute(route.id)}
                                  className="text-red-600 hover:text-red-700"
                                >
                                  <Trash2 size={16} />
                                </button>
                              </div>

                              <div className="space-y-2">
                                <input
                                  type="text"
                                  placeholder="Origin"
                                  value={route.origin}
                                  onChange={(e) => updateBusRoute(route.id, { origin: e.target.value })}
                                  className="w-full px-3 py-2 text-sm border rounded"
                                />
                                <input
                                  type="text"
                                  placeholder="Destination"
                                  value={route.destination}
                                  onChange={(e) => updateBusRoute(route.id, { destination: e.target.value })}
                                  className="w-full px-3 py-2 text-sm border rounded"
                                />
                                
                                <div className="grid grid-cols-3 gap-2">
                                  <div>
                                    <label className="text-xs text-gray-600">Buses</label>
                                    <input
                                      type="number"
                                      value={route.buses}
                                      onChange={(e) => updateBusRoute(route.id, { buses: parseInt(e.target.value) || 0 })}
                                      className="w-full px-2 py-1 text-sm border rounded"
                                      min="1"
                                    />
                                  </div>
                                  <div>
                                    <label className="text-xs text-gray-600">Capacity</label>
                                    <input
                                      type="number"
                                      value={route.capacity}
                                      onChange={(e) => updateBusRoute(route.id, { capacity: parseInt(e.target.value) || 0 })}
                                      className="w-full px-2 py-1 text-sm border rounded"
                                      min="1"
                                    />
                                  </div>
                                  <div>
                                    <label className="text-xs text-gray-600">Freq (min)</label>
                                    <input
                                      type="number"
                                      value={route.frequency}
                                      onChange={(e) => updateBusRoute(route.id, { frequency: parseInt(e.target.value) || 0 })}
                                      className="w-full px-2 py-1 text-sm border rounded"
                                      min="1"
                                    />
                                  </div>
                                </div>

                                <label className="flex items-center gap-2 text-sm">
                                  <input
                                    type="checkbox"
                                    checked={route.roundTrip}
                                    onChange={(e) => updateBusRoute(route.id, { roundTrip: e.target.checked })}
                                    className="w-4 h-4"
                                  />
                                  <span>Round Trip</span>
                                </label>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Evaluate Button */}
            {selectedModes.size > 0 && (
              <div className="space-y-4">
                <button
                  onClick={onEvaluate}
                  disabled={evaluating}
                  className="w-full flex items-center justify-center gap-2 px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors disabled:bg-gray-400 disabled:cursor-not-allowed"
                >
                  <PlayCircle size={20} />
                  <span>{evaluating ? 'Evaluating...' : 'Evaluate'}</span>
                </button>

                <button
                  onClick={onReset}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-100 transition-colors"
                >
                  <RotateCcw size={18} />
                  <span>Reset Configuration</span>
                </button>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
