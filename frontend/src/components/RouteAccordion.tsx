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
    <div className="panel-item">
      <button
        onClick={onHeaderClick}
        className="btn btn-ghost w-full justify-between"
      >
        <div className="flex items-center gap-3">
          {getModeIcon()}
          <div className="text-left">
            <div className="font-medium capitalize">{route.mode.replace('+', ' + ')}</div>
            <div className="text-sm text-muted">
              {route.totalDuration} • {route.totalDistance}
            </div>
          </div>
        </div>
        {expanded ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
      </button>

      {expanded && (
        <div className="mt-3 space-y-3">
          {route.segments.map((segment, index) => (
            <button
              key={index}
              onClick={() => onSegmentClick(segment.coordinates)}
              className="w-full text-left panel-item"
            >
              <div className="flex items-start gap-3">
                <div className="mt-1">{getSegmentIcon(segment)}</div>
                <div className="flex-1">
                  <div className="text-sm">{segment.instruction}</div>
                  <div className="text-xs text-muted mt-1">
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
