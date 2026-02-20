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
  const baseLayersRef = useRef<Record<string, L.TileLayer> | null>(null);
  const layerControlRef = useRef<L.Control.Layers | null>(null);
  const heatLayerRef = useRef<any>(null);
  const heatGroupRef = useRef<L.LayerGroup | null>(null);
  const originGroupRef = useRef<L.LayerGroup | null>(null);
  const destinationGroupRef = useRef<L.LayerGroup | null>(null);
  const markerRendererRef = useRef<L.Renderer | null>(null);

  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current) return;

    const map = L.map(mapContainerRef.current, { zoomControl: true }).setView(US_CENTER, US_ZOOM);
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
    heatGroupRef.current = L.layerGroup().addTo(map);
    originGroupRef.current = L.layerGroup().addTo(map);
    destinationGroupRef.current = L.layerGroup().addTo(map);
    layerControlRef.current = L.control
      .layers(
        baseLayersRef.current,
        {
          Heatmap: heatGroupRef.current,
          'Origin Points': originGroupRef.current,
          'Destination Points': destinationGroupRef.current
        },
        { position: 'topright', collapsed: true }
      )
      .addTo(map);
    mapRef.current = map;
    markerRendererRef.current = L.canvas();
    markerRendererRef.current.addTo(map);

    return () => {
      layerControlRef.current?.remove();
      layerControlRef.current = null;
      layerControlRef.current?.remove();
      layerControlRef.current = null;
      heatGroupRef.current = null;
      originGroupRef.current = null;
      destinationGroupRef.current = null;
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    if (heatLayerRef.current) {
      heatLayerRef.current.remove();
      heatLayerRef.current = null;
    }
    heatGroupRef.current?.clearLayers();

    if (!heatPoints.length) return;

    const points = heatPoints.map((p) => [p.lat, p.lng, p.intensity ?? 0.6]);
    heatLayerRef.current = (L as any).heatLayer(points, { radius: 20, blur: 16, maxZoom: 12 });
    heatLayerRef.current.addTo(heatGroupRef.current ?? map);
    const bounds = L.latLngBounds(heatPoints.map((p) => [p.lat, p.lng] as [number, number]));
    if (bounds.isValid()) {
      map.fitBounds(bounds, { padding: [30, 30] });
    }
  }, [heatPoints]);

  useEffect(() => {
    if (!originGroupRef.current || !destinationGroupRef.current) return;
    originGroupRef.current.clearLayers();
    destinationGroupRef.current.clearLayers();

    originPoints.forEach((point) => {
      L.circleMarker([point.lat, point.lng], {
        radius: 2.5,
        color: '#2563eb',
        weight: 1,
        fillColor: '#60a5fa',
        fillOpacity: 0.7,
        renderer: markerRendererRef.current ?? undefined,
        interactive: false
      }).addTo(originGroupRef.current!);
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
      }).addTo(destinationGroupRef.current!);
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

  return <div ref={mapContainerRef} className="w-full h-full relative z-0" />;
}
