import { ChevronDown, ChevronUp, Car, Bus, Navigation } from 'lucide-react';
import { Route, RouteSegment } from '../services/api';

interface RouteAccordionProps {
  route: Route;
  expanded: boolean;
  onHeaderClick: () => void;
  onSegmentClick: (coordinates: [number, number][]) => void;
}

export function RouteAccordion({ route, expanded, onHeaderClick, onSegmentClick }: RouteAccordionProps) {
  const getModeIcon = () => {
    if (route.mode.includes('bus')) return <Bus size={20} />;
    if (route.mode.includes('on-demand') || route.mode.includes('car')) return <Car size={20} />;
    return <Navigation size={20} />;
  };

  const getSegmentIcon = (segment: RouteSegment) => {
    switch (segment.type) {
      case 'drive':
        return <Car size={16} />;
      case 'transit':
        return <Bus size={16} />;
      case 'walk':
        return <Navigation size={16} />;
      default:
        return null;
    }
  };

  return (
    <div className="border rounded-lg overflow-hidden">
      <button
        onClick={onHeaderClick}
        className="w-full px-4 py-3 bg-gray-50 hover:bg-gray-100 flex items-center justify-between transition-colors"
      >
        <div className="flex items-center gap-3">
          {getModeIcon()}
          <div className="text-left">
            <div className="font-medium capitalize">{route.mode.replace('+', ' + ')}</div>
            <div className="text-sm text-gray-600">
              {route.totalDuration} • {route.totalDistance}
            </div>
          </div>
        </div>
        {expanded ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
      </button>

      {expanded && (
        <div className="p-4 bg-white space-y-3">
          {route.segments.map((segment, index) => (
            <button
              key={index}
              onClick={() => onSegmentClick(segment.coordinates)}
              className="w-full text-left p-3 rounded-lg hover:bg-gray-50 transition-colors border"
            >
              <div className="flex items-start gap-3">
                <div className="mt-1">{getSegmentIcon(segment)}</div>
                <div className="flex-1">
                  <div className="text-sm">{segment.instruction}</div>
                  <div className="text-xs text-gray-600 mt-1">
                    {segment.distance} • {segment.duration}
                  </div>
                </div>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}