import { useState, useRef, useEffect } from 'react';
import { Car, Bus, Shuffle, Navigation, ChevronLeft, ChevronRight } from 'lucide-react';
import { AutocompleteResult, Route } from '../services/api';
import { RouteAccordion } from './RouteAccordion';

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
    <div className={`${isCollapsed ? 'w-16' : 'w-96'} h-full bg-white border-r transition-all duration-300 relative flex flex-col`}>
      {/* Collapse Button */}
      <div className={`flex items-center ${isCollapsed ? 'justify-center py-4' : 'justify-between p-4'} border-b`}>
        {!isCollapsed && <h2 className="text-lg font-semibold truncate">Plan your Trip</h2>}
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
            Plan Trip
          </div>
        </div>
      )}

      {/* Main Content */}
      {!isCollapsed && (
        <>
          <div className="p-6 w-full flex-1 overflow-y-auto">


            {/* Origin Input */}
            <div className="mb-4 relative">
              <label className="block text-sm mb-2">Origin</label>
              <input
                ref={originInputRef}
                type="text"
                value={originQuery}
                onChange={(e) => {
                  setOriginQuery(e.target.value);
                }}
                className="w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Enter starting location"
              />
            </div>

            {/* Destination Input */}
            <div className="mb-6 relative">
              <label className="block text-sm mb-2">Destination</label>
              <input
                ref={destinationInputRef}
                type="text"
                value={destinationQuery}
                onChange={(e) => {
                  setDestinationQuery(e.target.value);
                }}
                className="w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Enter destination"
              />
            </div>

            {/* Mode Selection */}
            <div className="mb-6">
              <label className="block text-sm mb-3">Travel Mode</label>
              <div className="grid grid-cols-2 gap-3">
                <button
                  onClick={() => handleSelectMode('car')}
                  className={`flex items-center justify-center gap-2 px-4 py-3 rounded-lg border-2 transition-colors ${
                    selectedMode === 'car'
                      ? 'border-blue-500 bg-blue-50 text-blue-700'
                      : 'border-gray-300 hover:border-gray-400'
                  }`}
                >
                  <Car size={20} />
                  <span>Car</span>
                </button>
                <button
                  onClick={() => handleSelectMode('on-demand')}
                  className={`flex items-center justify-center gap-2 px-4 py-3 rounded-lg border-2 transition-colors ${
                    selectedMode === 'on-demand'
                      ? 'border-blue-500 bg-blue-50 text-blue-700'
                      : 'border-gray-300 hover:border-gray-400'
                  }`}
                >
                  <Car size={20} />
                  <span>On-Demand</span>
                </button>
                <button
                  onClick={() => handleSelectMode('bus')}
                  className={`flex items-center justify-center gap-2 px-4 py-3 rounded-lg border-2 transition-colors ${
                    selectedMode === 'bus'
                      ? 'border-blue-500 bg-blue-50 text-blue-700'
                      : 'border-gray-300 hover:border-gray-400'
                  }`}
                >
                  <Bus size={20} />
                  <span>Bus</span>
                </button>
                <button
                  onClick={() => handleSelectMode('car+bus')}
                  className={`flex items-center justify-center gap-2 px-4 py-3 rounded-lg border-2 transition-colors ${
                    selectedMode === 'car+bus'
                      ? 'border-blue-500 bg-blue-50 text-blue-700'
                      : 'border-gray-300 hover:border-gray-400'
                  }`}
                >
                  <Shuffle size={20} />
                  <span>Car+Bus</span>
                </button>
              </div>
            </div>

            {/* Navigate Button */}
            <div className="space-y-4">
              <button
                onClick={handleNavigate}
                disabled={!selectedOrigin || !selectedDestination || loading}
                className="w-full flex items-center justify-center gap-2 px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
              >
                <Navigation size={20} />
                <span>{loading ? 'Loading...' : 'Navigate'}</span>
              </button>

              <button
                onClick={onReset}
                className="w-full flex items-center justify-center gap-2 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-100 transition-colors"
              >
                <RotateCcw size={18} />
                <span>Reset</span>
              </button>
            </div>

            {/* Routes */}
            {routes.length > 0 && (
              <div className="mt-6">
                <h3 className="text-lg mb-4">Routes</h3>
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
          </div>
        </>
      )}
    </div>
  );
}
