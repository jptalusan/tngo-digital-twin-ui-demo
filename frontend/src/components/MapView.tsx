import { useEffect, useRef } from 'react';
import L from 'leaflet';

// Inline critical Leaflet CSS to avoid import issues
const leafletStyles = `
  .leaflet-container {
    font-family: inherit;
  }
  .leaflet-control-attribution {
    font-size: 10px;
  }
`;

export interface Marker {
  id: string;
  coordinates: [number, number];
  type: 'origin' | 'destination' | 'depot';
  label?: string;
  description?: string;
}

export interface RoutePolyline {
  id: string;
  coordinates: [number, number][];
  color: string;
  weight?: number;
  opacity?: number;
  dashArray?: string;
}

export interface MapLayer {
  id: string;
  type: 'polygon' | 'heatmap' | 'boundary';
  data: any;
  visible: boolean;
}

interface MapViewProps {
  markers: Marker[];
  routes: RoutePolyline[];
  onMapClick?: (coordinates: [number, number]) => void;
  onMapRightClick?: (coordinates: [number, number], x: number, y: number) => void;
  highlightedSegment?: [number, number][];
  layers?: MapLayer[];
}

export function MapView({ markers, routes, onMapClick, onMapRightClick, highlightedSegment, layers = [] }: MapViewProps) {
  const mapRef = useRef<L.Map | null>(null);
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const markersLayerRef = useRef<L.LayerGroup | null>(null);
  const routesLayerRef = useRef<L.LayerGroup | null>(null);
  const highlightLayerRef = useRef<L.Polyline | null>(null);
  const layersGroupRef = useRef<L.LayerGroup | null>(null);
  const lastBoundsRef = useRef<string>('');
  const resizeObserverRef = useRef<ResizeObserver | null>(null);

  // Initialize map
  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current) return;

    const map = L.map(mapContainerRef.current).setView([35.1495, -90.0490], 12);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap contributors'
    }).addTo(map);

    mapRef.current = map;
    markersLayerRef.current = L.layerGroup().addTo(map);
    routesLayerRef.current = L.layerGroup().addTo(map);
    layersGroupRef.current = L.layerGroup().addTo(map);

    if (typeof ResizeObserver !== 'undefined') {
      resizeObserverRef.current = new ResizeObserver(() => {
        map.invalidateSize();
      });
      resizeObserverRef.current.observe(mapContainerRef.current);
    }

    return () => {
      resizeObserverRef.current?.disconnect();
      resizeObserverRef.current = null;
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // Handle map clicks
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !onMapClick) return;

    const handleClick = (e: L.LeafletMouseEvent) => {
      onMapClick([e.latlng.lat, e.latlng.lng]);
    };

    map.on('click', handleClick);

    return () => {
      map.off('click', handleClick);
    };
  }, [onMapClick]);

  // Handle map right-clicks
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !onMapRightClick) return;

    const handleContextMenu = (e: L.LeafletMouseEvent) => {
      if (e.originalEvent?.preventDefault) {
        e.originalEvent.preventDefault();
      }
      onMapRightClick([e.latlng.lat, e.latlng.lng], e.originalEvent.clientX, e.originalEvent.clientY);
    };

    map.on('contextmenu', handleContextMenu);

    return () => {
      map.off('contextmenu', handleContextMenu);
    };
  }, [onMapRightClick]);

  // Update markers
  useEffect(() => {
    if (!markersLayerRef.current) return;

    markersLayerRef.current.clearLayers();

    markers.forEach(marker => {
      let markerIcon: L.DivIcon;

      if (marker.type === 'origin') {
        markerIcon = L.divIcon({
          className: 'custom-marker',
          html: '<div style="width: 20px; height: 20px; background-color: #22c55e; border: 3px solid white; border-radius: 50%; box-shadow: 0 2px 4px rgba(0,0,0,0.3);"></div>',
          iconSize: [20, 20],
          iconAnchor: [10, 10]
        });
      } else if (marker.type === 'destination') {
        markerIcon = L.divIcon({
          className: 'custom-marker',
          html: '<div style="width: 0; height: 0; border-left: 10px solid transparent; border-right: 10px solid transparent; border-bottom: 20px solid #ef4444; filter: drop-shadow(0 2px 4px rgba(0,0,0,0.3));"></div>',
          iconSize: [20, 20],
          iconAnchor: [10, 20]
        });
      } else {
        // depot
        markerIcon = L.divIcon({
          className: 'custom-marker',
          html: `<div style="padding: 4px 8px; background-color: #3b82f6; color: white; border-radius: 4px; font-size: 12px; font-weight: 600; box-shadow: 0 2px 4px rgba(0,0,0,0.3); white-space: nowrap;">${marker.label || 'Depot'}</div>`,
          iconSize: [40, 20],
          iconAnchor: [20, 10]
        });
      }

      const markerInstance = L.marker(marker.coordinates, { icon: markerIcon }).addTo(markersLayerRef.current!);

      // Bind popup if description exists
      if (marker.description) {
        markerInstance.bindPopup(`
          <div class="px-3 py-2 bg-white rounded-md min-w-[200px]">
            <h3 class="font-bold text-sm mb-1 capitalize text-gray-900">${marker.type}</h3>
            <p class="text-sm text-gray-600 leading-relaxed">${marker.description}</p>
          </div>
        `, {
          className: 'custom-popup',
          closeButton: false
        });
      }
    });

    // Auto-zoom only on initial load (if no routes are present) or if specifically requested
    // We remove the automatic re-zoom on marker updates to prevent "jarring" experience
    if (markers.length > 0 && mapRef.current && !routesLayerRef.current?.getLayers().length) {
       // Only zoom if we haven't zoomed before (rudimentary check) or if it's the very first marker
       // For now, disabling completely to satisfy "remove zooming in" request
    }
  }, [markers]);

  // Update routes
  useEffect(() => {
    if (!routesLayerRef.current) return;

    routesLayerRef.current.clearLayers();

    routes.forEach(route => {
      L.polyline(route.coordinates, {
        color: route.color,
        weight: route.weight || 4,
        opacity: route.opacity || 0.7,
        dashArray: route.dashArray
      }).addTo(routesLayerRef.current!);
    });

    // Auto-zoom to fit routes
    if (routes.length > 0 && mapRef.current) {
      const allCoords = routes.flatMap(r => r.coordinates);
      if (allCoords.length > 0) {
        const bounds = L.latLngBounds(allCoords);
        const boundsKey = bounds.toBBoxString();
        
        if (boundsKey !== lastBoundsRef.current) {
          mapRef.current.fitBounds(bounds, { padding: [50, 50] });
          lastBoundsRef.current = boundsKey;
        }
      }
    }
  }, [routes, markers.length]);

  // Update highlighted segment
  useEffect(() => {
    if (!mapRef.current) return;

    // Remove previous highlight
    if (highlightLayerRef.current) {
      highlightLayerRef.current.remove();
      highlightLayerRef.current = null;
    }

    if (highlightedSegment && highlightedSegment.length > 0) {
      const highlightLine = L.polyline(highlightedSegment, {
        color: '#fbbf24',
        weight: 6,
        opacity: 0.9
      }).addTo(mapRef.current);

      highlightLayerRef.current = highlightLine;
    }
  }, [highlightedSegment]);

  // Update evaluation layers
  useEffect(() => {
    if (!layersGroupRef.current) return;

    layersGroupRef.current.clearLayers();

    layers.forEach(layer => {
      if (!layer.visible) return;

      if (layer.type === 'polygon' && layer.data) {
        // Coverage area
        layer.data.forEach((polygon: [number, number][]) => {
          L.polygon(polygon, {
            color: '#10b981',
            fillColor: '#10b981',
            fillOpacity: 0.2,
            weight: 2
          }).addTo(layersGroupRef.current!);
        });
      } else if (layer.type === 'heatmap' && layer.data) {
        // Heatmap (using circle markers with varying opacity)
        layer.data.forEach((point: { coordinates: [number, number]; intensity: number }) => {
          L.circleMarker(point.coordinates, {
            radius: 8,
            fillColor: '#ef4444',
            color: '#ef4444',
            weight: 0,
            fillOpacity: point.intensity * 0.6
          }).addTo(layersGroupRef.current!);
        });
      } else if (layer.type === 'boundary' && layer.data) {
        // Service boundaries
        layer.data.forEach((polygon: [number, number][]) => {
          L.polygon(polygon, {
            color: '#3b82f6',
            fillColor: '#3b82f6',
            fillOpacity: 0.15,
            weight: 2,
            dashArray: '5, 5'
          }).addTo(layersGroupRef.current!);
        });
      }
    });
  }, [layers]);

  return <div ref={mapContainerRef} className="w-full h-full" />;
}
