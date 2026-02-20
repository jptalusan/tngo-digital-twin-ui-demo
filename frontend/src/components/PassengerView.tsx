import { useState, useRef, useEffect } from 'react';
import { Car, Bus, Shuffle, Navigation } from 'lucide-react';
import { AutocompleteResult, Route } from '../services/api';
import { RouteAccordion } from './RouteAccordion';
import { SidebarShell } from './SidebarShell';

import { RotateCcw } from 'lucide-react';

interface PassengerViewProps {
  origin: AutocompleteResult | null;
  destination: AutocompleteResult | null;
  onOriginChange: (location: AutocompleteResult | null) => void;
  onDestinationChange: (location: AutocompleteResult | null) => void;
  onNavigate: (
    mode: 'on-demand' | 'bus' | 'car+bus' | 'car',
    payload: { origin: [number, number]; destination: [number, number] }
  ) => void;
  routes: Route[];
  loading: boolean;
  onRouteClick: (route: Route) => void;
  onSegmentClick: (coordinates: [number, number][]) => void;
  onReset: () => void;
}

export function PassengerView({
  origin,
  destination,
  onOriginChange,
  onDestinationChange,
  onNavigate,
  routes,
  loading,
  onRouteClick,
  onSegmentClick,
  onReset
}: PassengerViewProps) {
  const [originQuery, setOriginQuery] = useState('');
  const [destinationQuery, setDestinationQuery] = useState('');
  const [selectedOrigin, setSelectedOrigin] = useState<AutocompleteResult | null>(null);
  const [selectedDestination, setSelectedDestination] = useState<AutocompleteResult | null>(null);
  const [selectedMode, setSelectedMode] = useState<'on-demand' | 'bus' | 'car+bus' | 'car'>('car');
  const [expandedRoute, setExpandedRoute] = useState<number | null>(0);
  const [isCollapsed, setIsCollapsed] = useState(false);

  const originInputRef = useRef<HTMLInputElement>(null);
  const destinationInputRef = useRef<HTMLInputElement>(null);

  // Sync props to state when they change externally (e.g. from map context menu)
  useEffect(() => {
    if (origin) {
      setSelectedOrigin(origin);
      setOriginQuery(origin.name);
    } else {
      // Only clear if explicitly null and not just initial render if we want persistence
      // But for now strict sync is safer
      if (selectedOrigin) {
        setSelectedOrigin(null);
        setOriginQuery('');
      }
    }
  }, [origin]);

  useEffect(() => {
    if (destination) {
      setSelectedDestination(destination);
      setDestinationQuery(destination.name);
    } else {
      if (selectedDestination) {
        setSelectedDestination(null);
        setDestinationQuery('');
      }
    }
  }, [destination]);

  const handleSelectMode = (mode: 'on-demand' | 'bus' | 'car+bus' | 'car') => {
    setSelectedMode(mode);
  };

  const parseCoordinates = (value: string): [number, number] | null => {
    const parts = value.split(',').map((part) => Number(part.trim()));
    if (parts.length !== 2) return null;
    if (parts.some((num) => Number.isNaN(num))) return null;
    return [parts[0], parts[1]];
  };

  const handleNavigate = () => {
    let nextOrigin = selectedOrigin;
    let nextDestination = selectedDestination;

    if (!nextOrigin) {
      const coordinates = parseCoordinates(originQuery);
      if (coordinates) {
        nextOrigin = {
          id: `typed-origin-${Date.now()}`,
          name: originQuery,
          coordinates
        };
        setSelectedOrigin(nextOrigin);
        onOriginChange(nextOrigin);
      }
    }

    if (!nextDestination) {
      const coordinates = parseCoordinates(destinationQuery);
      if (coordinates) {
        nextDestination = {
          id: `typed-destination-${Date.now()}`,
          name: destinationQuery,
          coordinates
        };
        setSelectedDestination(nextDestination);
        onDestinationChange(nextDestination);
      }
    }

    if (nextOrigin && nextDestination) {
      console.log('[passenger] navigate origin:', nextOrigin.coordinates);
      console.log('[passenger] navigate destination:', nextDestination.coordinates);
      onNavigate(selectedMode, {
        origin: nextOrigin.coordinates,
        destination: nextDestination.coordinates
      });
    }
  };

  const handleRouteHeaderClick = (route: Route, index: number) => {
    if (expandedRoute === index) {
      setExpandedRoute(null);
    } else {
      setExpandedRoute(index);
      onRouteClick(route);
    }
  };

  return (
    <SidebarShell
      title="Passenger View"
      subtitle="Trip planning and routing"
      collapsible
      collapsed={isCollapsed}
      onToggleCollapse={() => setIsCollapsed(!isCollapsed)}
      collapsedLabel="Passenger"
      headerAction={loading ? <span className="control-chip">Routing</span> : undefined}
    >
      <div className="panel space-y-4">
        <div className="panel-title">Trip Setup</div>
        <div className="control">
          <label className="control-label">Origin</label>
          <input
            ref={originInputRef}
            type="text"
            value={originQuery}
            onChange={(e) => {
              setOriginQuery(e.target.value);
            }}
            className="control-input"
            placeholder="Enter starting location"
          />
        </div>
        <div className="control">
          <label className="control-label">Destination</label>
          <input
            ref={destinationInputRef}
            type="text"
            value={destinationQuery}
            onChange={(e) => {
              setDestinationQuery(e.target.value);
            }}
            className="control-input"
            placeholder="Enter destination"
          />
        </div>
      </div>

      <div className="panel space-y-3">
        <div className="panel-title">Travel Mode</div>
        <div className="grid grid-cols-2 gap-2">
          {[
            { id: 'car', label: 'Car', icon: Car },
            { id: 'on-demand', label: 'On-Demand', icon: Car },
            { id: 'bus', label: 'Bus', icon: Bus },
            { id: 'car+bus', label: 'Car + Bus', icon: Shuffle }
          ].map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              type="button"
              onClick={() => handleSelectMode(id as typeof selectedMode)}
              data-active={selectedMode === id}
              className="btn btn-outline w-full justify-start"
            >
              <Icon size={16} />
              <span>{label}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="panel space-y-3">
        <div className="panel-title">Actions</div>
        <button
          onClick={handleNavigate}
          disabled={!selectedOrigin || !selectedDestination || loading}
          className="btn btn-primary w-full"
        >
          <Navigation size={16} />
          <span>{loading ? 'Loading...' : 'Navigate'}</span>
        </button>
        <button onClick={onReset} className="btn btn-outline w-full">
          <RotateCcw size={16} />
          <span>Reset</span>
        </button>
      </div>

      {routes.length > 0 && (
        <div className="panel space-y-3">
          <div className="panel-title">
            <span>Routes</span>
            <span className="tag">{routes.length} options</span>
          </div>
          <div className="space-y-3">
            {routes.map((route, index) => (
              <RouteAccordion
                key={index}
                route={route}
                expanded={expandedRoute === index}
                onHeaderClick={() => handleRouteHeaderClick(route, index)}
                onSegmentClick={onSegmentClick}
              />
            ))}
          </div>
        </div>
      )}
    </SidebarShell>
  );
}
