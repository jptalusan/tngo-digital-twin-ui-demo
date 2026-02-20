import { useEffect, useMemo, useRef } from 'react';
import L from 'leaflet';

type FeatureCollection = {
  type: 'FeatureCollection';
  features: any[];
};

type Feature = {
  type: 'Feature';
  properties?: Record<string, any>;
  geometry: any;
};

export type MoveODStateSelection = {
  state_fips: string;
  state_name?: string;
  state_abbr?: string;
};

export type MoveODCountySelection = {
  geoid: string;
  name?: string;
  state_fips?: string;
  county_fips?: string;
};

interface MoveODMapProps {
  baseMapStyle?: 'standard' | 'light';
  statesGeoJSON: FeatureCollection | null;
  countiesGeoJSON?: FeatureCollection | null;
  selectedCountyGeoJSON?: Feature | FeatureCollection | null;
  highlightedStateFips?: string | null;
  syntheticDemandPoints?: Array<[number, number]>;
  showFill?: boolean;
  onStateClick?: (state: MoveODStateSelection) => void;
  onCountyClick?: (county: MoveODCountySelection) => void;
}

const US_CENTER: [number, number] = [39.5, -98.35];
const US_ZOOM = 4;

const getProp = (props: Record<string, any>, keys: string[]) => {
  for (const key of keys) {
    const value = props?.[key];
    if (value !== undefined && value !== null && value !== '') {
      return value;
    }
  }
  return undefined;
};

const normalizeStateFips = (value: any) => {
  if (value === undefined || value === null) return '';
  const raw = String(value).trim();
  if (!raw) return '';
  return raw.padStart(2, '0');
};

const extractStateSelection = (feature: Feature): MoveODStateSelection | null => {
  const props = feature?.properties ?? {};
  const fips = normalizeStateFips(
    getProp(props, ['state_fips', 'STATEFP', 'STATEFP10', 'STATEFP00', 'STATE_FIPS', 'STATE'])
  );
  if (!fips) return null;
  const state_name = getProp(props, ['state_name', 'name', 'NAME', 'STATE_NAME', 'NAMELSAD']) as string | undefined;
  const state_abbr = getProp(props, ['state_abbr', 'STUSPS', 'STATE_ABBR']) as string | undefined;
  return { state_fips: fips, state_name, state_abbr };
};

const extractCountySelection = (feature: Feature): MoveODCountySelection | null => {
  const props = feature?.properties ?? {};
  const geoid = getProp(props, ['geoid', 'GEOID', 'GEOID10', 'GEOID20']) as string | undefined;
  if (!geoid) return null;
  const name = getProp(props, ['name', 'NAME', 'county_name']) as string | undefined;
  const state_fips = normalizeStateFips(getProp(props, ['state_fips', 'STATEFP', 'STATEFP10', 'STATEFP20']));
  const county_fips = getProp(props, ['county_fips', 'COUNTYFP', 'COUNTYFP10', 'COUNTYFP20']) as
    | string
    | undefined;
  return { geoid, name, state_fips, county_fips };
};

export function MoveODMap({
  baseMapStyle = 'light',
  statesGeoJSON,
  countiesGeoJSON,
  selectedCountyGeoJSON,
  highlightedStateFips,
  syntheticDemandPoints = [],
  showFill = true,
  onStateClick,
  onCountyClick
}: MoveODMapProps) {
  const mapRef = useRef<L.Map | null>(null);
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const tileLayerRef = useRef<L.TileLayer | null>(null);
  const statesLayerRef = useRef<L.GeoJSON | null>(null);
  const countiesLayerRef = useRef<L.GeoJSON | null>(null);
  const selectedCountyLayerRef = useRef<L.GeoJSON | null>(null);
  const syntheticLayerRef = useRef<L.LayerGroup | null>(null);
  const syntheticRendererRef = useRef<L.Renderer | null>(null);
  const resizeObserverRef = useRef<ResizeObserver | null>(null);

  const stateStyle = useMemo(
    () => (feature: any) => {
      const selection = feature ? extractStateSelection(feature as Feature) : null;
      const isHighlighted =
        selection?.state_fips && highlightedStateFips
          ? selection.state_fips === highlightedStateFips
          : false;
      const strokeWeight = showFill ? (isHighlighted ? 2 : 1.5) : isHighlighted ? 3.5 : 2.5;
      return {
        color: isHighlighted ? '#0ea5e9' : '#94a3b8',
        weight: strokeWeight,
        fillColor: isHighlighted ? '#7dd3fc' : '#e2e8f0',
        fillOpacity: showFill ? (isHighlighted ? 0.45 : 0.15) : 0
      } as L.PathOptions;
    },
    [highlightedStateFips, showFill]
  );

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
    if (!map.getPane('moveod-demand')) {
      const pane = map.createPane('moveod-demand');
      if (pane) {
        pane.style.zIndex = '650';
        pane.style.pointerEvents = 'none';
      }
    }
    syntheticLayerRef.current = L.layerGroup().addTo(map);
    syntheticRendererRef.current = L.canvas();
    syntheticRendererRef.current.addTo(map);

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

    if (statesLayerRef.current) {
      statesLayerRef.current.remove();
      statesLayerRef.current = null;
    }

    if (!statesGeoJSON) return;

    const layer = L.geoJSON(statesGeoJSON as any, {
      style: stateStyle as any,
      interactive: true,
      onEachFeature: (feature, layerInstance) => {
        if (!onStateClick) return;
        layerInstance.on('click', () => {
          const selection = extractStateSelection(feature as Feature);
          if (selection) {
            onStateClick(selection);
          }
        });
      }
    });

    statesLayerRef.current = layer;
    layer.addTo(map);
  }, [statesGeoJSON, onStateClick, stateStyle]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    if (countiesLayerRef.current) {
      countiesLayerRef.current.remove();
      countiesLayerRef.current = null;
    }

    if (!countiesGeoJSON) return;

    const layer = L.geoJSON(countiesGeoJSON as any, {
      style: {
        color: '#cbd5f5',
        weight: showFill ? 0.7 : 2,
        fillColor: '#e2e8f0',
        fillOpacity: showFill ? 0.08 : 0
      } as L.PathOptions,
      interactive: !!onCountyClick,
      onEachFeature: (feature, layerInstance) => {
        if (!onCountyClick) return;
        layerInstance.on('click', () => {
          const selection = extractCountySelection(feature as Feature);
          if (selection) {
            onCountyClick(selection);
          }
        });
      }
    });

    countiesLayerRef.current = layer;
    layer.addTo(map);
  }, [countiesGeoJSON, showFill, onCountyClick]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    if (selectedCountyLayerRef.current) {
      selectedCountyLayerRef.current.remove();
      selectedCountyLayerRef.current = null;
    }

    if (!selectedCountyGeoJSON) return;

    const layer = L.geoJSON(selectedCountyGeoJSON as any, {
      style: {
        color: '#f97316',
        weight: showFill ? 2.5 : 3.5,
        fillColor: '#fdba74',
        fillOpacity: showFill ? 0.45 : 0
      } as L.PathOptions,
      interactive: false
    });

    selectedCountyLayerRef.current = layer;
    layer.addTo(map);

    const bounds = layer.getBounds();
    if (bounds.isValid()) {
      map.fitBounds(bounds, { padding: [30, 30] });
    }
  }, [selectedCountyGeoJSON, showFill]);

  useEffect(() => {
    if (!syntheticLayerRef.current) return;
    syntheticLayerRef.current.clearLayers();

    if (!syntheticDemandPoints.length) return;

    syntheticDemandPoints.forEach((point) => {
      L.circleMarker(point, {
        radius: 2.5,
        color: '#1d4ed8',
        weight: 1,
        fillColor: '#60a5fa',
        fillOpacity: 0.6,
        renderer: syntheticRendererRef.current ?? undefined,
        pane: 'moveod-demand',
        interactive: false
      }).addTo(syntheticLayerRef.current!);
    });
  }, [syntheticDemandPoints]);

  return <div ref={mapContainerRef} className="w-full h-full" />;
}
