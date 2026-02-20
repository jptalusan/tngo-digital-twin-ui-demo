import { useEffect, useRef } from 'react';
import L from 'leaflet';
import '../vendor/leaflet-heat';

export type HeatPoint = { lat: number; lng: number; intensity?: number };
export type MarkerPoint = { lat: number; lng: number };

interface MoveODAnalysisMapProps {
  baseMapStyle?: 'standard' | 'light';
  heatPoints: HeatPoint[];
  originPoints?: MarkerPoint[];
  destinationPoints?: MarkerPoint[];
}

const US_CENTER: [number, number] = [39.5, -98.35];
const US_ZOOM = 4;

export function MoveODAnalysisMap({
  baseMapStyle = 'light',
  heatPoints,
  originPoints = [],
  destinationPoints = []
}: MoveODAnalysisMapProps) {
  const mapRef = useRef<L.Map | null>(null);
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const tileLayerRef = useRef<L.TileLayer | null>(null);
  const heatLayerRef = useRef<any>(null);
  const originLayerRef = useRef<L.LayerGroup | null>(null);
  const destinationLayerRef = useRef<L.LayerGroup | null>(null);
  const markerRendererRef = useRef<L.Renderer | null>(null);

  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current) return;

    const map = L.map(mapContainerRef.current, { zoomControl: true }).setView(US_CENTER, US_ZOOM);
    const standardLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap contributors'
    });
    const lightLayer = L.tileLayer('https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png', {
      attribution: '© OpenStreetMap contributors © CARTO'
    });
    tileLayerRef.current = baseMapStyle === 'light' ? lightLayer : standardLayer;
    tileLayerRef.current.addTo(map);
    mapRef.current = map;
    originLayerRef.current = L.layerGroup().addTo(map);
    destinationLayerRef.current = L.layerGroup().addTo(map);
    markerRendererRef.current = L.canvas();
    markerRendererRef.current.addTo(map);

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const nextLayer = baseMapStyle === 'light'
      ? L.tileLayer('https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png', {
          attribution: '© OpenStreetMap contributors © CARTO'
        })
      : L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
          attribution: '© OpenStreetMap contributors'
        });

    if (tileLayerRef.current) {
      map.removeLayer(tileLayerRef.current);
    }
    tileLayerRef.current = nextLayer;
    tileLayerRef.current.addTo(map);
  }, [baseMapStyle]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    if (heatLayerRef.current) {
      map.removeLayer(heatLayerRef.current);
      heatLayerRef.current = null;
    }

    if (!heatPoints.length) return;

    const points = heatPoints.map((p) => [p.lat, p.lng, p.intensity ?? 0.6]);
    heatLayerRef.current = (L as any).heatLayer(points, { radius: 20, blur: 16, maxZoom: 12 });
    heatLayerRef.current.addTo(map);
    const bounds = L.latLngBounds(heatPoints.map((p) => [p.lat, p.lng] as [number, number]));
    if (bounds.isValid()) {
      map.fitBounds(bounds, { padding: [30, 30] });
    }
  }, [heatPoints]);

  useEffect(() => {
    if (!originLayerRef.current || !destinationLayerRef.current) return;
    originLayerRef.current.clearLayers();
    destinationLayerRef.current.clearLayers();

    originPoints.forEach((point) => {
      L.circleMarker([point.lat, point.lng], {
        radius: 2.5,
        color: '#2563eb',
        weight: 1,
        fillColor: '#60a5fa',
        fillOpacity: 0.7,
        renderer: markerRendererRef.current ?? undefined,
        interactive: false
      }).addTo(originLayerRef.current!);
    });

    destinationPoints.forEach((point) => {
      L.circleMarker([point.lat, point.lng], {
        radius: 2.5,
        color: '#dc2626',
        weight: 1,
        fillColor: '#fca5a5',
        fillOpacity: 0.7,
        renderer: markerRendererRef.current ?? undefined,
        interactive: false
      }).addTo(destinationLayerRef.current!);
    });

    const map = mapRef.current;
    if (!map) return;
    const combined = [...originPoints, ...destinationPoints];
    if (combined.length === 0) return;
    const bounds = L.latLngBounds(combined.map((point) => [point.lat, point.lng] as [number, number]));
    if (bounds.isValid()) {
      map.fitBounds(bounds, { padding: [30, 30] });
    }
  }, [originPoints, destinationPoints]);

  return <div ref={mapContainerRef} className="w-full h-full" />;
}
