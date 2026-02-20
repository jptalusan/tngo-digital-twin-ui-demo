import { useEffect, useRef } from 'react';
import L from 'leaflet';
import * as h3 from 'h3-js';

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
  type: 'origin' | 'destination' | 'depot' | 'gtfs-stop' | 'demand-home' | 'demand-work';
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
  outlineColor?: string;
  outlineWeight?: number;
  outlineOpacity?: number;
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
  baseMapStyle?: 'standard' | 'light';
  showHexGrid?: boolean;
  hexDisplayMode?: 'grid' | 'established-only';
  selectedHexes?: string[];
  establishedHexes?: string[];
  activeHexes?: string[];
  onHexClick?: (hexId: string) => void;
  allowMapPan?: boolean;
  onBoundsChange?: (bounds: { south: number; west: number; north: number; east: number }) => void;
}

export function MapView({
  markers,
  routes,
  onMapClick,
  onMapRightClick,
  highlightedSegment,
  layers = [],
  baseMapStyle = 'standard',
  showHexGrid = false,
  hexDisplayMode = 'grid',
  selectedHexes = [],
  establishedHexes = [],
  activeHexes = [],
  onHexClick,
  allowMapPan = true,
  onBoundsChange
}: MapViewProps) {
  const mapRef = useRef<L.Map | null>(null);
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const markersLayerRef = useRef<L.LayerGroup | null>(null);
  const routesLayerRef = useRef<L.LayerGroup | null>(null);
  const highlightLayerRef = useRef<L.Polyline | null>(null);
  const hexLayerRef = useRef<L.LayerGroup | null>(null);
  const baseLayersRef = useRef<Record<string, L.TileLayer> | null>(null);
  const layerControlRef = useRef<L.Control.Layers | null>(null);
  const overlayRegistryRef = useRef<Set<string>>(new Set());
  const dynamicLayerGroupsRef = useRef<Map<string, L.LayerGroup>>(new Map());
  const markerRendererRef = useRef<L.Renderer | null>(null);
  const lastBoundsRef = useRef<string>('');
  const resizeObserverRef = useRef<ResizeObserver | null>(null);

  // Initialize map
  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current) return;

    const map = L.map(mapContainerRef.current).setView([35.1495, -90.0490], 12);

    if (!map.getPane('hexes')) {
      const pane = map.createPane('hexes');
      if (pane) {
        pane.style.zIndex = '450';
        pane.style.pointerEvents = 'auto';
      }
    }

    const standardLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '© OpenStreetMap contributors'
    });
    const hotLayer = L.tileLayer('https://{s}.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution:
        '© OpenStreetMap contributors, Tiles style by Humanitarian OpenStreetMap Team hosted by OpenStreetMap France'
    });
    const lightLayer = L.tileLayer('https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png', {
      maxZoom: 19,
      attribution: '© OpenStreetMap contributors © CARTO'
    });

    baseLayersRef.current = {
      'OSM Standard': standardLayer,
      'OSM Humanitarian': hotLayer,
      'Light (No Labels)': lightLayer
    };
    const initialLayer = baseMapStyle === 'light' ? lightLayer : standardLayer;
    initialLayer.addTo(map);
    layerControlRef.current = L.control
      .layers(baseLayersRef.current, undefined, { position: 'topright', collapsed: true })
      .addTo(map);

    mapRef.current = map;
    markersLayerRef.current = L.layerGroup().addTo(map);
    routesLayerRef.current = L.layerGroup().addTo(map);
    hexLayerRef.current = L.layerGroup({ pane: 'hexes' });
    markerRendererRef.current = L.canvas();
    markerRendererRef.current.addTo(map);

    const addOverlay = (id: string, layer: L.Layer, label: string) => {
      if (!layerControlRef.current || overlayRegistryRef.current.has(id)) return;
      layerControlRef.current.addOverlay(layer, label);
      overlayRegistryRef.current.add(id);
    };

    addOverlay('overlay:markers', markersLayerRef.current, 'Markers');
    addOverlay('overlay:routes', routesLayerRef.current, 'Routes');

    if (typeof ResizeObserver !== 'undefined') {
      resizeObserverRef.current = new ResizeObserver(() => {
        map.invalidateSize();
      });
      resizeObserverRef.current.observe(mapContainerRef.current);
    }

    return () => {
      resizeObserverRef.current?.disconnect();
      resizeObserverRef.current = null;
      layerControlRef.current?.remove();
      layerControlRef.current = null;
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    const hexLayer = hexLayerRef.current;
    if (!map || !hexLayer) return;

    if (showHexGrid && layerControlRef.current && !overlayRegistryRef.current.has('overlay:hexes')) {
      layerControlRef.current.addOverlay(hexLayer, 'Hex Grid');
      overlayRegistryRef.current.add('overlay:hexes');
    }

    if (showHexGrid) {
      if (!map.hasLayer(hexLayer)) {
        hexLayer.addTo(map);
      }
    } else if (map.hasLayer(hexLayer)) {
      map.removeLayer(hexLayer);
    }

    const parseBounds = () => {
      const raw = (import.meta.env.VITE_DEMAND_HEX_BOUNDS as string | undefined) ?? '';
      if (!raw) return null;
      const parts = raw.split(',').map((part) => Number(part.trim()));
      if (parts.length !== 4 || parts.some((value) => Number.isNaN(value))) return null;
      const [minLat, minLng, maxLat, maxLng] = parts;
      return L.latLngBounds([minLat, minLng], [maxLat, maxLng]);
    };

    const defaultBounds = L.latLngBounds([34.9829, -90.3103], [36.6781, -81.6469]);
    const regionBounds = parseBounds() ?? defaultBounds;
    const rawResolution = Number((import.meta.env.VITE_DEMAND_HEX_RES as string | undefined) ?? 7);
    const hexResolution = Number.isFinite(rawResolution) ? Math.max(0, Math.min(15, rawResolution)) : 7;

    const buildHexes = () => {
      if (!showHexGrid) {
        hexLayer.clearLayers();
        return;
      }

      const viewBounds = map.getBounds();
      if (!regionBounds.intersects(viewBounds)) {
        hexLayer.clearLayers();
        return;
      }

      let hexes: string[] = [];
      if (hexDisplayMode === 'established-only') {
        const combined = new Set<string>([...selectedHexes, ...establishedHexes, ...activeHexes]);
        hexes = Array.from(combined).filter((hexId) => {
          try {
            const [lat, lng] = h3.cellToLatLng(hexId);
            return viewBounds.contains([lat, lng]);
          } catch {
            return false;
          }
        });
      } else {
        const viewSW = viewBounds.getSouthWest();
        const viewNE = viewBounds.getNorthEast();
        const regionSW = regionBounds.getSouthWest();
        const regionNE = regionBounds.getNorthEast();
        const southWest = L.latLng(
          Math.max(viewSW.lat, regionSW.lat),
          Math.max(viewSW.lng, regionSW.lng)
        );
        const northEast = L.latLng(
          Math.min(viewNE.lat, regionNE.lat),
          Math.min(viewNE.lng, regionNE.lng)
        );
        const boundary: [number, number][] = [
          [southWest.lat, southWest.lng],
          [southWest.lat, northEast.lng],
          [northEast.lat, northEast.lng],
          [northEast.lat, southWest.lng],
          [southWest.lat, southWest.lng]
        ];

        try {
          // Use lat/lng boundary array to avoid GeoJSON option mismatches.
          hexes = h3.polygonToCells([boundary], hexResolution);
        } catch (error) {
          console.warn('[hex] failed to build hex grid', error);
          hexLayer.clearLayers();
          return;
        }
      }
      hexLayer.clearLayers();
      const selected = new Set(selectedHexes);
      const established = new Set(establishedHexes);
      const active = new Set(activeHexes);

      hexes.forEach((hexId) => {
        const isSelected = selected.has(hexId);
        const isEstablished = established.has(hexId);
        const isActive = active.has(hexId);
        const boundary = h3.cellToBoundary(hexId, true).map(([lng, lat]) => [lat, lng] as [number, number]);
        const polygon = L.polygon(boundary, {
          color: isActive
            ? '#1d4ed8'
            : isEstablished
            ? '#b91c1c'
            : isSelected
            ? '#1d4ed8'
            : '#2563eb',
          weight: isActive ? 2 : isSelected ? 2 : 1,
          opacity: isActive ? 0.9 : isSelected ? 0.9 : 0.5,
          fillColor: isActive
            ? '#60a5fa'
            : isEstablished
            ? '#fca5a5'
            : isSelected
            ? '#60a5fa'
            : '#93c5fd',
          fillOpacity: isActive ? 0.35 : isEstablished ? 0.4 : isSelected ? 0.35 : 0.12,
          interactive: false,
          bubblingMouseEvents: false,
          pane: 'hexes'
        });
        polygon.on('pointerdown', (event: L.LeafletMouseEvent) => {
          if (event.originalEvent) {
            L.DomEvent.stopPropagation(event.originalEvent);
          }
        });
        polygon.addTo(hexLayer);
      });
    };

    buildHexes();
    map.on('moveend zoomend', buildHexes);

    return () => {
      map.off('moveend zoomend', buildHexes);
      hexLayer.clearLayers();
    };
  }, [showHexGrid, hexDisplayMode, selectedHexes, establishedHexes, activeHexes, onHexClick]);

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

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (allowMapPan) {
      map.dragging.enable();
      map.scrollWheelZoom.enable();
      map.doubleClickZoom.enable();
      map.boxZoom.enable();
    } else {
      map.dragging.disable();
      map.scrollWheelZoom.disable();
      map.doubleClickZoom.disable();
      map.boxZoom.disable();
    }
  }, [allowMapPan]);

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

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !onBoundsChange) return;

    const emitBounds = () => {
      const bounds = map.getBounds();
      const sw = bounds.getSouthWest();
      const ne = bounds.getNorthEast();
      onBoundsChange({
        south: sw.lat,
        west: sw.lng,
        north: ne.lat,
        east: ne.lng
      });
    };

    emitBounds();
    map.on('moveend zoomend', emitBounds);

    return () => {
      map.off('moveend zoomend', emitBounds);
    };
  }, [onBoundsChange]);

  // Update markers
  useEffect(() => {
    if (!markersLayerRef.current) return;

    markersLayerRef.current.clearLayers();

    markers.forEach(marker => {
      if (marker.type === 'gtfs-stop' || marker.type === 'demand-home' || marker.type === 'demand-work') {
        const isHome = marker.type === 'demand-home';
        const isGtfs = marker.type === 'gtfs-stop';
        L.circleMarker(marker.coordinates, {
          radius: isGtfs ? 5 : 3,
          color: isGtfs ? '#7c2d12' : isHome ? '#c2410c' : '#9a3412',
          weight: 2,
          fillColor: isGtfs ? '#fbbf24' : isHome ? '#fdba74' : '#fb923c',
          fillOpacity: 1,
          renderer: markerRendererRef.current ?? undefined,
          interactive: false,
          pane: isGtfs ? 'markerPane' : 'overlayPane'
        }).addTo(markersLayerRef.current!);
        return;
      }

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
          html: `
            <div style="position: relative; width: 22px; height: 24px;">
              <div style="position: absolute; left: 3px; top: 2px; width: 2px; height: 20px; background: #1f2937;"></div>
              <div style="position: absolute; left: 5px; top: 2px; width: 14px; height: 10px; background: #ef4444; clip-path: polygon(0 0, 100% 12%, 80% 50%, 100% 88%, 0 100%); box-shadow: 0 2px 4px rgba(0,0,0,0.3);"></div>
              <div style="position: absolute; left: 1px; top: 20px; width: 6px; height: 2px; background: #1f2937; border-radius: 2px;"></div>
            </div>
          `,
          iconSize: [22, 24],
          iconAnchor: [5, 22]
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
          <div class="popup-card">
            <h3>${marker.type}</h3>
            <p>${marker.description}</p>
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
      if (route.outlineColor && route.outlineWeight) {
        L.polyline(route.coordinates, {
          color: route.outlineColor,
          weight: route.outlineWeight,
          opacity: route.outlineOpacity ?? 0.9,
          dashArray: route.dashArray
        }).addTo(routesLayerRef.current!);
      }
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
    const map = mapRef.current;
    if (!map || !layerControlRef.current) return;

    const formatLayerLabel = (id: string) =>
      id
        .replace(/[_-]+/g, ' ')
        .replace(/\b\w/g, (char) => char.toUpperCase());

    const addOverlay = (id: string, layer: L.Layer, label: string) => {
      if (overlayRegistryRef.current.has(id)) return;
      layerControlRef.current?.addOverlay(layer, label);
      overlayRegistryRef.current.add(id);
    };

    const nextIds = new Set(layers.map((layer) => layer.id));
    Array.from(dynamicLayerGroupsRef.current.entries()).forEach(([id, group]) => {
      if (!nextIds.has(id)) {
        group.clearLayers();
        if (map.hasLayer(group)) {
          map.removeLayer(group);
        }
        (layerControlRef.current as any)?.removeLayer?.(group);
        overlayRegistryRef.current.delete(`overlay:layer:${id}`);
        dynamicLayerGroupsRef.current.delete(id);
      }
    });

    layers.forEach((layer) => {
      let group = dynamicLayerGroupsRef.current.get(layer.id);
      if (!group) {
        group = L.layerGroup();
        dynamicLayerGroupsRef.current.set(layer.id, group);
        addOverlay(`overlay:layer:${layer.id}`, group, formatLayerLabel(layer.id));
      }

      if (layer.visible) {
        if (!map.hasLayer(group)) {
          group.addTo(map);
        }
      } else if (map.hasLayer(group)) {
        map.removeLayer(group);
      }

      group.clearLayers();

      if (!layer.visible) return;

      if (layer.type === 'polygon' && layer.data) {
        // Coverage area
        layer.data.forEach((polygon: [number, number][]) => {
          L.polygon(polygon, {
            color: '#10b981',
            fillColor: '#10b981',
            fillOpacity: 0.2,
            weight: 2
          }).addTo(group!);
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
          }).addTo(group!);
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
          }).addTo(group!);
        });
      }
    });
  }, [layers]);

  return <div ref={mapContainerRef} className="w-full h-full relative z-0" />;
}
