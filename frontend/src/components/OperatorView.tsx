import { useState, useRef } from 'react';
import { Car, Bus, Plus, Trash2, Upload, PlayCircle, ChevronDown, ChevronUp, RotateCcw } from 'lucide-react';
import { apiService } from '../services/api';
import { buildUrl } from '../services/http';
import { SidebarShell } from './SidebarShell';

export interface Depot {
  id: string;
  coordinates: [number, number];
  vehicles: number;
  capacity: number;
  address?: string;
  serviceZoneHexes?: string[];
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
  onRemoveDepot: (id: string) => void;
  depots: Depot[];
  onBusRouteUpdate: (routes: BusRoute[]) => void;
  onEvaluate: () => void;
  onReset: () => void;
  onStartDepotWizard: (defaults: { vehicles: number; capacity: number }) => void;
  depotWizardActive: boolean;
  onGtfsUploaded: (payload: { gtfs_id: string; gtfs_name: string; job_id: string; status: string }) => void;
  showDepotHexes: boolean;
  onToggleDepotHexes: (value: boolean) => void;
  demandModels: Array<{ id: string; label: string }>;
  selectedDemandModelId: string;
  demandSamplePercent: number;
  onDemandModelChange: (id: string) => void;
  onDemandSampleChange: (value: number) => void;
  evaluating?: boolean;
}

export function OperatorView({ 
  onRemoveDepot, 
  depots, 
  onBusRouteUpdate,
  onEvaluate,
  onReset,
  onStartDepotWizard,
  depotWizardActive,
  onGtfsUploaded,
  showDepotHexes,
  onToggleDepotHexes,
  demandModels,
  selectedDemandModelId,
  demandSamplePercent,
  onDemandModelChange,
  onDemandSampleChange,
  evaluating = false
}: OperatorViewProps) {
  const [selectedModes, setSelectedModes] = useState<Set<string>>(new Set());
  const [newDepotVehicles, setNewDepotVehicles] = useState(5);
  const [newDepotCapacity, setNewDepotCapacity] = useState(4);
  const [busRoutes, setBusRoutes] = useState<BusRoute[]>([]);
  const [activeBusRouteId, setActiveBusRouteId] = useState<string | null>(null);
  const [gtfsMode, setGtfsMode] = useState(false);
  const [gtfsUploading, setGtfsUploading] = useState(false);
  const [gtfsError, setGtfsError] = useState<string | null>(null);
  const [demandUploading, setDemandUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const demandFileInputRef = useRef<HTMLInputElement | null>(null);
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [onDemandExpanded, setOnDemandExpanded] = useState(true);
  const [busExpanded, setBusExpanded] = useState(true);
  const selectedDemandModel =
    demandModels.find((model) => model.id === selectedDemandModelId) ?? demandModels[0];

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
    onStartDepotWizard({ vehicles: newDepotVehicles, capacity: newDepotCapacity });
  };

  const handleGtfsFileSelected = async (file: File | null) => {
    if (!file) return;
    if (!file.name.toLowerCase().endsWith('.zip')) {
      setGtfsError('Please select a .zip file.');
      return;
    }
    setGtfsError(null);
    setGtfsUploading(true);
    try {
      const formData = new FormData();
      const gtfsName = file.name.replace(/\.zip$/i, '');
      formData.append('gtfs_name', gtfsName);
      formData.append('file', file);

      const response = await fetch(buildUrl('/gtfs/upload'), {
        method: 'POST',
        body: formData
      });

      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || response.statusText);
      }

      const payload = await response.json();
      console.log('[api] gtfs upload response:', payload);
      onGtfsUploaded(payload);
    } catch (error) {
      console.error('[api] gtfs upload error:', error);
      setGtfsError('Upload failed. Check console for details.');
    } finally {
      setGtfsUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const handleDemandFileSelected = (file: File | null) => {
    if (!file) return;
    setDemandUploading(true);
    console.log('[operator] demand upload placeholder:', file.name);
    window.setTimeout(() => {
      setDemandUploading(false);
      if (demandFileInputRef.current) {
        demandFileInputRef.current.value = '';
      }
    }, 1200);
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
    (window as any).handleOperatorSetOrigin = (coordinates: [number, number]) =>
      setRouteEndpoint('origin', coordinates);
    (window as any).handleOperatorSetDestination = (coordinates: [number, number]) =>
      setRouteEndpoint('destination', coordinates);
  }

  return (
    <div className="relative h-full">
      {demandUploading && (
        <div className="absolute inset-0 z-20 flex items-center justify-center overlay-scrim">
          <div className="floating-card text-sm font-medium">
            Uploading demand data...
          </div>
        </div>
      )}

      <SidebarShell
        title="Operator View"
        subtitle="Service modes, depots, and evaluation"
        collapsible
        collapsed={isCollapsed}
        onToggleCollapse={() => setIsCollapsed(!isCollapsed)}
        collapsedLabel="Operator"
        headerAction={evaluating ? <span className="control-chip">Evaluating</span> : undefined}
        footer={
          <div className="space-y-3">
            <button
              onClick={onEvaluate}
              disabled={evaluating}
              className="btn btn-primary w-full"
            >
              <PlayCircle size={16} />
              <span>{evaluating ? 'Evaluating...' : 'Evaluate'}</span>
            </button>
            <button onClick={onReset} className="btn btn-outline w-full">
              <RotateCcw size={16} />
              <span>Reset Configuration</span>
            </button>
          </div>
        }
      >
        <div className="panel space-y-4">
          <div className="panel-title">Demand Model</div>
          <select
            value={selectedDemandModelId}
            onChange={(e) => onDemandModelChange(e.target.value)}
            className="control-select"
            disabled={demandModels.length === 0}
          >
            {demandModels.map((model) => (
              <option key={model.id} value={model.id}>
                {model.label}
              </option>
            ))}
          </select>
          <div>
            <div className="flex items-center justify-between text-xs text-muted mb-2">
              <span>Sample</span>
              <span>{demandSamplePercent}%</span>
            </div>
            <input
              type="range"
              min={0}
              max={100}
              value={demandSamplePercent}
              onChange={(e) => onDemandSampleChange(parseInt(e.target.value) || 0)}
              className="w-full"
            />
          </div>
          <div>
            <input
              ref={demandFileInputRef}
              type="file"
              className="hidden"
              onChange={(e) => handleDemandFileSelected(e.target.files?.[0] ?? null)}
            />
            <button
              onClick={() => demandFileInputRef.current?.click()}
              disabled={demandUploading}
              className="btn btn-outline w-full"
            >
              <Upload size={16} />
              <span>{demandUploading ? 'Uploading...' : 'Upload Demand Data'}</span>
            </button>
          </div>
        </div>

        <div className="panel space-y-2">
          <div className="panel-title">Map Overlays</div>
          <label className="control-row">
            <span>Show Service Hex Grid</span>
            <input
              type="checkbox"
              checked={showDepotHexes}
              onChange={(e) => onToggleDepotHexes(e.target.checked)}
              className="h-4 w-4"
            />
          </label>
          <div className="control-hint">Hex grid always shows during depot selection.</div>
        </div>

        <div className="panel space-y-3">
          <div className="panel-title">Service Modes</div>
          <button
            onClick={() => toggleMode('on-demand')}
            className="btn btn-outline w-full justify-start"
            data-active={selectedModes.has('on-demand')}
          >
            <Car size={16} />
            <span>On-Demand</span>
          </button>
          <button
            onClick={() => toggleMode('bus')}
            className="btn btn-outline w-full justify-start"
            data-active={selectedModes.has('bus')}
          >
            <Bus size={16} />
            <span>Bus (Fixed Line)</span>
          </button>
        </div>

        {selectedModes.has('on-demand') && (
          <div className="panel space-y-3">
            <button
              onClick={() => setOnDemandExpanded(!onDemandExpanded)}
              className="panel-title w-full"
              type="button"
            >
              <span>On-Demand Configuration</span>
              {onDemandExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            </button>
            {onDemandExpanded && (
              <div className="space-y-3">
                <div className="control">
                  <label className="control-label">Vehicles per Depot</label>
                  <input
                    type="number"
                    value={newDepotVehicles}
                    onChange={(e) => setNewDepotVehicles(parseInt(e.target.value) || 0)}
                    className="control-input"
                    min="1"
                  />
                </div>
                <div className="control">
                  <label className="control-label">Vehicle Capacity</label>
                  <input
                    type="number"
                    value={newDepotCapacity}
                    onChange={(e) => setNewDepotCapacity(parseInt(e.target.value) || 0)}
                    className="control-input"
                    min="1"
                  />
                </div>
                <button
                  onClick={handleAddDepotClick}
                  disabled={depotWizardActive}
                  className="btn btn-primary w-full"
                >
                  <Plus size={16} />
                  <span>{depotWizardActive ? 'Adding Depot...' : 'Add Depot'}</span>
                </button>

                {depots.length > 0 && (
                  <div className="space-y-2">
                    <div className="panel-subtitle">Depots ({depots.length})</div>
                    {depots.map((depot, index) => (
                      <div key={depot.id} className="control-row">
                        <span>
                          Depot {index + 1}: {depot.vehicles} vehicles (cap: {depot.capacity})
                        </span>
                        <button
                          onClick={() => onRemoveDepot(depot.id)}
                          className="btn btn-ghost"
                          type="button"
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

        {selectedModes.has('bus') && (
          <div className="panel space-y-3">
            <button
              onClick={() => setBusExpanded(!busExpanded)}
              className="panel-title w-full"
              type="button"
            >
              <span>Fixed Line Configuration</span>
              {busExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            </button>
            {busExpanded && (
              <div className="space-y-3">
                <div className="grid grid-cols-2 gap-2">
                  <button
                    onClick={() => setGtfsMode(false)}
                    className="btn btn-outline w-full"
                    data-active={!gtfsMode}
                  >
                    Custom Routes
                  </button>
                  <button
                    onClick={() => setGtfsMode(true)}
                    className="btn btn-outline w-full"
                    data-active={gtfsMode}
                  >
                    Upload GTFS
                  </button>
                </div>

                {gtfsMode ? (
                  <div className="control-row flex-col items-start">
                    <div className="flex items-center gap-2">
                      <Upload size={20} />
                      <span className="text-sm font-semibold">Upload GTFS File</span>
                    </div>
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept=".zip,application/zip"
                      className="hidden"
                      onChange={(e) => handleGtfsFileSelected(e.target.files?.[0] ?? null)}
                    />
                    <button
                      onClick={() => fileInputRef.current?.click()}
                      disabled={gtfsUploading}
                      className="btn btn-primary w-full"
                    >
                      {gtfsUploading ? 'Uploading...' : 'Choose File'}
                    </button>
                    {gtfsError && <div className="warning-banner w-full">{gtfsError}</div>}
                  </div>
                ) : (
                  <div className="space-y-3">
                    <button onClick={addBusRoute} className="btn btn-primary w-full">
                      <Plus size={16} />
                      <span>Add Route</span>
                    </button>

                    <div className="space-y-3">
                      {busRoutes.map((route) => (
                        <div key={route.id} className="control-row flex-col items-start gap-3">
                          <div className="flex w-full items-center justify-between">
                            <span className="text-sm font-semibold">Route Configuration</span>
                            <button
                              onClick={() => removeBusRoute(route.id)}
                              className="btn btn-ghost"
                              type="button"
                            >
                              <Trash2 size={16} />
                            </button>
                          </div>

                          <div className="grid w-full gap-2">
                            <input
                              type="text"
                              placeholder="Origin"
                              value={route.origin}
                              onChange={(e) => updateBusRoute(route.id, { origin: e.target.value })}
                              className="control-input"
                            />
                            <input
                              type="text"
                              placeholder="Destination"
                              value={route.destination}
                              onChange={(e) => updateBusRoute(route.id, { destination: e.target.value })}
                              className="control-input"
                            />
                          </div>

                          <div className="grid w-full grid-cols-3 gap-2">
                            <div className="control">
                              <label className="control-label">Buses</label>
                              <input
                                type="number"
                                value={route.buses}
                                onChange={(e) => updateBusRoute(route.id, { buses: parseInt(e.target.value) || 0 })}
                                className="control-input"
                                min="1"
                              />
                            </div>
                            <div className="control">
                              <label className="control-label">Capacity</label>
                              <input
                                type="number"
                                value={route.capacity}
                                onChange={(e) => updateBusRoute(route.id, { capacity: parseInt(e.target.value) || 0 })}
                                className="control-input"
                                min="1"
                              />
                            </div>
                            <div className="control">
                              <label className="control-label">Freq (min)</label>
                              <input
                                type="number"
                                value={route.frequency}
                                onChange={(e) => updateBusRoute(route.id, { frequency: parseInt(e.target.value) || 0 })}
                                className="control-input"
                                min="1"
                              />
                            </div>
                          </div>

                          <label className="control-row w-full">
                            <span>Round Trip</span>
                            <input
                              type="checkbox"
                              checked={route.roundTrip}
                              onChange={(e) => updateBusRoute(route.id, { roundTrip: e.target.checked })}
                              className="h-4 w-4"
                            />
                          </label>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </SidebarShell>
    </div>
  );
}
