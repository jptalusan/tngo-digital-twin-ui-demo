import { useState, useRef, useEffect } from 'react';
import { Car, Bus, Shuffle, Navigation, ChevronLeft, ChevronRight } from 'lucide-react';
import { apiService, AutocompleteResult, Route } from '../services/api';
import { RouteAccordion } from './RouteAccordion';

import { RotateCcw } from 'lucide-react';

interface PassengerViewProps {
  origin: AutocompleteResult | null;
  destination: AutocompleteResult | null;
  onOriginChange: (location: AutocompleteResult | null) => void;
  onDestinationChange: (location: AutocompleteResult | null) => void;
  onNavigate: (modes: string[]) => void;
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
  const [originSuggestions, setOriginSuggestions] = useState<AutocompleteResult[]>([]);
  const [destinationSuggestions, setDestinationSuggestions] = useState<AutocompleteResult[]>([]);
  const [selectedOrigin, setSelectedOrigin] = useState<AutocompleteResult | null>(null);
  const [selectedDestination, setSelectedDestination] = useState<AutocompleteResult | null>(null);
  const [showOriginSuggestions, setShowOriginSuggestions] = useState(false);
  const [showDestinationSuggestions, setShowDestinationSuggestions] = useState(false);
  const [selectedModes, setSelectedModes] = useState<Set<string>>(new Set(['car']));
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

  // Autocomplete for origin
  useEffect(() => {
    const fetchSuggestions = async () => {
      if (originQuery.length > 0) {
        const results = await apiService.autocomplete(originQuery);
        setOriginSuggestions(results);
      } else {
        setOriginSuggestions([]);
      }
    };

    const timer = setTimeout(fetchSuggestions, 300);
    return () => clearTimeout(timer);
  }, [originQuery]);

  // Autocomplete for destination
  useEffect(() => {
    const fetchSuggestions = async () => {
      if (destinationQuery.length > 0) {
        const results = await apiService.autocomplete(destinationQuery);
        setDestinationSuggestions(results);
      } else {
        setDestinationSuggestions([]);
      }
    };

    const timer = setTimeout(fetchSuggestions, 300);
    return () => clearTimeout(timer);
  }, [destinationQuery]);

  const handleOriginSelect = (suggestion: AutocompleteResult) => {
    setSelectedOrigin(suggestion);
    setOriginQuery(suggestion.name);
    setShowOriginSuggestions(false);
    onOriginChange(suggestion);
  };

  const handleDestinationSelect = (suggestion: AutocompleteResult) => {
    setSelectedDestination(suggestion);
    setDestinationQuery(suggestion.name);
    setShowDestinationSuggestions(false);
    onDestinationChange(suggestion);
  };

  const toggleMode = (mode: string) => {
    const newModes = new Set(selectedModes);
    if (newModes.has(mode)) {
      newModes.delete(mode);
    } else {
      newModes.add(mode);
    }
    setSelectedModes(newModes);
  };

  const handleNavigate = () => {
    if (selectedOrigin && selectedDestination && selectedModes.size > 0) {
      onNavigate(Array.from(selectedModes));
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
                  setShowOriginSuggestions(true);
                }}
                onFocus={() => setShowOriginSuggestions(true)}
                className="w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Enter starting location"
              />
              {showOriginSuggestions && originSuggestions.length > 0 && (
                <div className="absolute z-10 w-full mt-1 bg-white border rounded-lg shadow-lg max-h-48 overflow-y-auto">
                  {originSuggestions.map((suggestion) => (
                    <button
                      key={suggestion.id}
                      onClick={() => handleOriginSelect(suggestion)}
                      className="w-full px-4 py-2 text-left hover:bg-gray-100"
                    >
                      {suggestion.name}
                    </button>
                  ))}
                </div>
              )}
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
                  setShowDestinationSuggestions(true);
                }}
                onFocus={() => setShowDestinationSuggestions(true)}
                className="w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Enter destination"
              />
              {showDestinationSuggestions && destinationSuggestions.length > 0 && (
                <div className="absolute z-10 w-full mt-1 bg-white border rounded-lg shadow-lg max-h-48 overflow-y-auto">
                  {destinationSuggestions.map((suggestion) => (
                    <button
                      key={suggestion.id}
                      onClick={() => handleDestinationSelect(suggestion)}
                      className="w-full px-4 py-2 text-left hover:bg-gray-100"
                    >
                      {suggestion.name}
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Mode Selection */}
            <div className="mb-6">
              <label className="block text-sm mb-3">Travel Mode</label>
              <div className="grid grid-cols-2 gap-3">
                <button
                  onClick={() => toggleMode('car')}
                  className={`flex items-center justify-center gap-2 px-4 py-3 rounded-lg border-2 transition-colors ${
                    selectedModes.has('car')
                      ? 'border-blue-500 bg-blue-50 text-blue-700'
                      : 'border-gray-300 hover:border-gray-400'
                  }`}
                >
                  <Car size={20} />
                  <span>Car</span>
                </button>
                <button
                  onClick={() => toggleMode('on-demand')}
                  className={`flex items-center justify-center gap-2 px-4 py-3 rounded-lg border-2 transition-colors ${
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
                  className={`flex items-center justify-center gap-2 px-4 py-3 rounded-lg border-2 transition-colors ${
                    selectedModes.has('bus')
                      ? 'border-blue-500 bg-blue-50 text-blue-700'
                      : 'border-gray-300 hover:border-gray-400'
                  }`}
                >
                  <Bus size={20} />
                  <span>Bus</span>
                </button>
                <button
                  onClick={() => toggleMode('car+bus')}
                  className={`flex items-center justify-center gap-2 px-4 py-3 rounded-lg border-2 transition-colors ${
                    selectedModes.has('car+bus')
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
                disabled={!selectedOrigin || !selectedDestination || selectedModes.size === 0 || loading}
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