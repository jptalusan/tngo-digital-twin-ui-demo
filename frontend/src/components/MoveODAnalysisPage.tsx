import { useCallback, useEffect, useMemo, useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import { MoveODAnalysisMap, HeatPoint } from './MoveODAnalysisMap';
import { useAnalysisJobs } from '../state/analysisJobs';
import { SidebarShell } from './SidebarShell';

export type MoveODAnalysisSelection = {
  state_fips: string;
  state_name?: string;
  county_geoid: string;
  county_name?: string;
  county_fips: string;
};

type AvailableArea = {
  state_fips: string;
  state_name?: string;
  county_geoid?: string;
  county_fips: string;
  county_name?: string;
};

type ChartDatum = { label: string; value: number };

type AnalysisData = {
  originHeat: any[];
  destinationHeat: any[];
  departureBins: any[];
  arrivalBins: any[];
  travelTimeBins: any[];
  topOrigins: any[];
  flowBalance: any[];
};

type AnalysisAvailability = {
  originHeat: boolean;
  destinationHeat: boolean;
  departureBins: boolean;
  arrivalBins: boolean;
  travelTimeBins: boolean;
  topOrigins: boolean;
  flowBalance: boolean;
};

const apiBase =
  (import.meta.env.VITE_API_URL as string | undefined) ??
  (typeof window !== 'undefined' ? window.location.origin : '');

const fetchJson = async (path: string, signal?: AbortSignal) => {
  const response = await fetch(`${apiBase}${path}`, { signal });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json();
};

const normalizeChartData = (items: any[]): ChartDatum[] => {
  if (!Array.isArray(items)) return [];
  return items
    .map((item) => {
      if (item == null) return null;
      if (typeof item === 'number') return { label: String(item), value: item };
      const labelCandidates = [
        item.label,
        item.bin,
        item.bucket,
        item.hour,
        item.name,
        item.origin,
        item.origin_geoid,
        item.origin_name,
        item.origin_id,
        item.origin_zone,
        item.origin_taz,
        item.taz,
        item.zone,
        item.category,
        item.id
      ];
      const label =
        labelCandidates.find((value: unknown) => value !== undefined && value !== null && String(value).trim() !== '') ??
        'Unknown';
      const value =
        item.value ??
        item.count ??
        item.total ??
        item.frequency ??
        item.n ??
        0;
      return { label: String(label), value: Number(value) };
    })
    .filter(Boolean) as ChartDatum[];
};

const normalizeHeatPoints = (items: any[]): HeatPoint[] => {
  if (!Array.isArray(items)) return [];
  return items
    .map((item) => {
      if (!item) return null;
      if (Array.isArray(item) && item.length >= 2) {
        const [lat, lng, intensity] = item;
        if (Number.isFinite(lat) && Number.isFinite(lng)) {
          return { lat, lng, intensity: Number.isFinite(intensity) ? intensity : 0.6 };
        }
        return null;
      }
      if (item.coordinates && Array.isArray(item.coordinates)) {
        const [lon, lat] = item.coordinates;
        return { lat, lng: lon, intensity: item.intensity ?? item.weight ?? 0.6 };
      }
      if (typeof item.lat === 'number' && typeof item.lon === 'number') {
        return { lat: item.lat, lng: item.lon, intensity: item.intensity ?? item.weight ?? 0.6 };
      }
      if (typeof item.latitude === 'number' && typeof item.longitude === 'number') {
        return { lat: item.latitude, lng: item.longitude, intensity: item.intensity ?? 0.6 };
      }
      return null;
    })
    .filter(Boolean) as HeatPoint[];
};

interface MoveODAnalysisPageProps {
  selection: MoveODAnalysisSelection | null;
  baseMapStyle?: 'standard' | 'light';
}

const views = [
  { id: 'map-default', label: 'Map (Points)' },
  { id: 'heatmap-origin', label: 'Heatmap (Origin)' },
  { id: 'heatmap-destination', label: 'Heatmap (Destination)' },
  { id: 'departure-bins', label: 'Departure Times' },
  { id: 'arrival-bins', label: 'Arrival Times' },
  { id: 'travel-time-bins', label: 'Travel Times' },
  { id: 'top-origins', label: 'Top Origins' },
  { id: 'flow-balance', label: 'Flow Balance' }
] as const;

type ViewId = (typeof views)[number]['id'];

export function MoveODAnalysisPage({ selection, baseMapStyle = 'light' }: MoveODAnalysisPageProps) {
  const [activeView, setActiveView] = useState<ViewId>('map-default');
  const [data, setData] = useState<AnalysisData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [availability, setAvailability] = useState<AnalysisAvailability>({
    originHeat: false,
    destinationHeat: false,
    departureBins: false,
    arrivalBins: false,
    travelTimeBins: false,
    topOrigins: false,
    flowBalance: false
  });
  const [availableAreas, setAvailableAreas] = useState<AvailableArea[]>([]);
  const [selectedStateFips, setSelectedStateFips] = useState<string>('');
  const [selectedCountyGeoid, setSelectedCountyGeoid] = useState<string>('');
  const [analyzing, setAnalyzing] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [originPoints, setOriginPoints] = useState<Array<{ lat: number; lng: number }>>([]);
  const [destinationPoints, setDestinationPoints] = useState<Array<{ lat: number; lng: number }>>([]);
  const [pointVisibilityPercent, setPointVisibilityPercent] = useState(100);
  const [showOriginPoints, setShowOriginPoints] = useState(true);
  const [showDestinationPoints, setShowDestinationPoints] = useState(true);
  const { jobs, startJob } = useAnalysisJobs();

  const normalizedAreas = useMemo(() => {
    const flattened: AvailableArea[] = [];
    availableAreas.forEach((item: any) => {
      if (Array.isArray(item?.counties)) {
        item.counties.forEach((county: any) => {
          flattened.push({
            state_fips: item.state_fips,
            state_name: item.state_name,
            county_geoid: county.geoid,
            county_fips: county.county_fips,
            county_name: county.county_name
          });
        });
      } else {
        flattened.push(item);
      }
    });
    return flattened.map((item) => ({
      state_fips: item.state_fips,
      state_name: item.state_name,
      county_geoid: item.county_geoid ?? `${item.state_fips}${item.county_fips}`,
      county_fips: item.county_fips,
      county_name: item.county_name
    }));
  }, [availableAreas]);

  const states = useMemo(() => {
    const map = new Map<string, { state_fips: string; state_name?: string }>();
    normalizedAreas.forEach((area) => {
      if (!map.has(area.state_fips)) {
        map.set(area.state_fips, { state_fips: area.state_fips, state_name: area.state_name });
      }
    });
    return Array.from(map.values()).sort((a, b) => (a.state_name ?? a.state_fips).localeCompare(b.state_name ?? b.state_fips));
  }, [normalizedAreas]);

  const counties = useMemo(() => {
    if (!selectedStateFips) return [];
    return normalizedAreas
      .filter((area) => area.state_fips === selectedStateFips)
      .sort((a, b) => (a.county_name ?? a.county_fips).localeCompare(b.county_name ?? b.county_fips));
  }, [normalizedAreas, selectedStateFips]);

  const activeSelection = useMemo(() => {
    if (selectedStateFips && selectedCountyGeoid) {
      const match = normalizedAreas.find((area) => area.county_geoid === selectedCountyGeoid);
      if (match) {
        return {
          state_fips: match.state_fips,
          state_name: match.state_name,
          county_geoid: match.county_geoid ?? selectedCountyGeoid,
          county_name: match.county_name,
          county_fips: match.county_fips
        } as MoveODAnalysisSelection;
      }
      return {
        state_fips: selectedStateFips,
        state_name: selection?.state_name,
        county_geoid: selectedCountyGeoid,
        county_name: selection?.county_name,
        county_fips: selectedCountyGeoid.slice(2)
      } as MoveODAnalysisSelection;
    }
    if (selection) return selection;
    return null;
  }, [normalizedAreas, selectedStateFips, selectedCountyGeoid, selection]);

  const fetchAnalysis = useCallback(async (signal?: AbortSignal) => {
    if (!activeSelection) return;
    setLoading(true);
    setError(null);
    setAvailability({
      originHeat: false,
      destinationHeat: false,
      departureBins: false,
      arrivalBins: false,
      travelTimeBins: false,
      topOrigins: false,
      flowBalance: false
    });

    try {
      const base = '/api/moveod/analysis';

      const results = await Promise.allSettled([
        fetchJson(`${base}/heatmap?kind=origin&state_fips=${activeSelection.state_fips}&county_fips=${activeSelection.county_fips}`, signal),
        fetchJson(`${base}/heatmap?kind=destination&state_fips=${activeSelection.state_fips}&county_fips=${activeSelection.county_fips}`, signal),
        fetchJson(`${base}/departure-bins?state_fips=${activeSelection.state_fips}&county_fips=${activeSelection.county_fips}&kind=departure`, signal),
        fetchJson(`${base}/departure-bins?state_fips=${activeSelection.state_fips}&county_fips=${activeSelection.county_fips}&kind=arrival`, signal),
        fetchJson(`${base}/travel-time-bins?state_fips=${activeSelection.state_fips}&county_fips=${activeSelection.county_fips}`, signal),
        fetchJson(`${base}/top-origins?state_fips=${activeSelection.state_fips}&county_fips=${activeSelection.county_fips}`, signal),
        fetchJson(`${base}/flow-balance?state_fips=${activeSelection.state_fips}&county_fips=${activeSelection.county_fips}`, signal)
      ]);

      const unwrap = (payload: any) => (Array.isArray(payload?.items) ? payload.items : payload ?? []);

      const resolved = results.map((result) => (result.status === 'fulfilled' ? result.value : null));

      const [
        originHeat,
        destinationHeat,
        departureBins,
        arrivalBins,
        travelTimeBins,
        topOrigins,
        flowBalance
      ] = resolved;

      setData({
        originHeat: unwrap(originHeat),
        destinationHeat: unwrap(destinationHeat),
        departureBins: unwrap(departureBins),
        arrivalBins: unwrap(arrivalBins),
        travelTimeBins: unwrap(travelTimeBins),
        topOrigins: unwrap(topOrigins),
        flowBalance: unwrap(flowBalance)
      });

      setAvailability({
        originHeat: !!originHeat,
        destinationHeat: !!destinationHeat,
        departureBins: !!departureBins,
        arrivalBins: !!arrivalBins,
        travelTimeBins: !!travelTimeBins,
        topOrigins: !!topOrigins,
        flowBalance: !!flowBalance
      });
    } catch (err: any) {
      if (err?.name === 'AbortError') return;
      setError(typeof err?.message === 'string' ? err.message : 'Failed to load analysis');
    } finally {
      setLoading(false);
    }
  }, [activeSelection]);

  useEffect(() => {
    if (!activeSelection) {
      setOriginPoints([]);
      setDestinationPoints([]);
      setPointVisibilityPercent(100);
      return;
    }
    const controller = new AbortController();
    const limit = Number(import.meta.env.VITE_MOVEOD_ANALYSIS_POINTS_LIMIT ?? 800);
    fetchJson(`/api/moveod/synthetic-demand?state_fips=${activeSelection.state_fips}&county_fips=${activeSelection.county_fips}&limit=${limit}`, controller.signal)
      .then((payload) => {
        const items = Array.isArray(payload?.items) ? payload.items : payload ?? [];
        const nextOrigins: Array<{ lat: number; lng: number }> = [];
        const nextDestinations: Array<{ lat: number; lng: number }> = [];
        items.forEach((item: any) => {
          const origin = item?.origin_location;
          if (origin?.type === 'Point' && Array.isArray(origin.coordinates)) {
            const [lon, lat] = origin.coordinates;
            if (Number.isFinite(lat) && Number.isFinite(lon)) {
              nextOrigins.push({ lat, lng: lon });
            }
          }
          const dest = item?.destination_location;
          if (dest?.type === 'Point' && Array.isArray(dest.coordinates)) {
            const [lon, lat] = dest.coordinates;
            if (Number.isFinite(lat) && Number.isFinite(lon)) {
              nextDestinations.push({ lat, lng: lon });
            }
          }
        });
        setOriginPoints(nextOrigins);
        setDestinationPoints(nextDestinations);
      })
      .catch(() => {
        setOriginPoints([]);
        setDestinationPoints([]);
      });
    return () => controller.abort();
  }, [activeSelection]);

  useEffect(() => {
    const controller = new AbortController();
    fetchJson('/api/moveod/analysis/available-areas-named', controller.signal)
      .then((payload) => {
        const items = Array.isArray(payload?.items) ? payload.items : payload ?? [];
        setAvailableAreas(items);
      })
      .catch((err: any) => {
        if (err?.name === 'AbortError') return;
        setError(typeof err?.message === 'string' ? err.message : 'Failed to load areas');
      });
    return () => controller.abort();
  }, [selection]);

  useEffect(() => {
    if (!selection) return;
    setSelectedStateFips(selection.state_fips);
    setSelectedCountyGeoid(selection.county_geoid);
  }, [selection]);

  useEffect(() => {
    if (!activeSelection) return;
    setActiveView('map-default');
    setData(null);
    setAvailability({
      originHeat: false,
      destinationHeat: false,
      departureBins: false,
      arrivalBins: false,
      travelTimeBins: false,
      topOrigins: false,
      flowBalance: false
    });
    setOriginPoints([]);
    setDestinationPoints([]);
    setPointVisibilityPercent(100);
    setShowOriginPoints(true);
    setShowDestinationPoints(true);
    setError(null);
    setAnalyzing(false);
    setJobId(null);
  }, [activeSelection?.state_fips, activeSelection?.county_fips, activeSelection?.county_geoid]);

  const handleAnalyze = useCallback(async () => {
    if (!activeSelection) {
      setError('Select a state and county before analyzing.');
      return;
    }
    setAnalyzing(true);
    setError(null);
    try {
      const response = await fetch(`${apiBase}/api/moveod/analyze?state_fips=${activeSelection.state_fips}&county_fips=${activeSelection.county_fips}`, { method: 'POST' });
      if (response.status === 202) {
        const payload = await response.json();
        const nextJobId = payload?.job_id ?? payload?.jobId;
        if (!nextJobId) {
          setAnalyzing(false);
          setError('Missing job_id from analyze response');
          return;
        }
        setJobId(nextJobId);
        startJob(nextJobId, activeSelection);
        return;
      }
      if (response.status === 200) {
        const payload = await response.json();
        if (payload?.message === 'already analyzed') {
          setAnalyzing(false);
          setJobId(null);
          void fetchAnalysis();
          return;
        }
      }
      if (!response.ok) {
        throw new Error(await response.text());
      }
      setAnalyzing(false);
    } catch (err: any) {
      setAnalyzing(false);
      setError(typeof err?.message === 'string' ? err.message : 'Analyze failed');
    }
  }, [activeSelection, fetchAnalysis, startJob]);

  const activeJob = useMemo(() => {
    if (!jobId) return null;
    return jobs.find((job) => job.jobId === jobId) ?? null;
  }, [jobs, jobId]);

  useEffect(() => {
    if (!jobId || !activeJob) return;
    if (activeJob.status === 'done') {
      setAnalyzing(false);
      setJobId(null);
      void fetchAnalysis();
      return;
    }
    if (activeJob.status === 'error') {
      setAnalyzing(false);
      setJobId(null);
      setError(activeJob.message ?? 'Analysis failed');
    }
  }, [activeJob, fetchAnalysis, jobId]);

  const originHeat = useMemo(() => normalizeHeatPoints(data?.originHeat ?? []), [data]);
  const destinationHeat = useMemo(() => normalizeHeatPoints(data?.destinationHeat ?? []), [data]);
  const departureBins = useMemo(() => normalizeChartData(data?.departureBins ?? []), [data]);
  const arrivalBins = useMemo(() => normalizeChartData(data?.arrivalBins ?? []), [data]);
  const travelTimeBins = useMemo(() => {
    const items = normalizeChartData(data?.travelTimeBins ?? []);
    const order = [
      'under_5_minutes',
      '5_to_9_minutes',
      '10_to_14_minutes',
      '15_to_19_minutes',
      '20_to_24_minutes',
      '25_to_29_minutes',
      '30_to_34_minutes',
      '35_to_39_minutes',
      '40_to_44_minutes',
      '45_to_49_minutes',
      '50_to_54_minutes',
      '55_to_59_minutes',
      '60_to_64_minutes',
      '65_to_69_minutes',
      '70_to_74_minutes',
      '75_to_79_minutes',
      '80_to_84_minutes',
      '85_to_89_minutes',
      '90_minutes_and_over'
    ];
    const index = new Map(order.map((label, i) => [label, i]));
    return [...items].sort((a, b) => {
      const ai = index.get(a.label);
      const bi = index.get(b.label);
      if (ai === undefined && bi === undefined) return a.label.localeCompare(b.label);
      if (ai === undefined) return 1;
      if (bi === undefined) return -1;
      return ai - bi;
    });
  }, [data]);
  const topOrigins = useMemo(() => normalizeChartData(data?.topOrigins ?? []), [data]);
  const flowBalance = useMemo(() => normalizeChartData(data?.flowBalance ?? []), [data]);

  const visibleOriginPoints = useMemo(() => {
    const clamped = Math.min(100, Math.max(0, pointVisibilityPercent));
    const count = Math.round(originPoints.length * (clamped / 100));
    return originPoints.slice(0, count);
  }, [originPoints, pointVisibilityPercent]);

  const visibleDestinationPoints = useMemo(() => {
    const clamped = Math.min(100, Math.max(0, pointVisibilityPercent));
    const count = Math.round(destinationPoints.length * (clamped / 100));
    return destinationPoints.slice(0, count);
  }, [destinationPoints, pointVisibilityPercent]);

  const renderChart = (items: ChartDatum[], title: string) => (
    <div className="h-full w-full flex flex-col">
      <div className="text-sm font-semibold text-strong mb-3">{title}</div>
      <div className="flex-1" style={{ minHeight: 280 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={items} margin={{ top: 10, right: 20, left: 0, bottom: 10 }}>
            <XAxis dataKey="label" tick={{ fontSize: 10 }} interval={0} angle={-30} textAnchor="end" height={60} />
            <YAxis tick={{ fontSize: 10 }} width={30} />
            <Tooltip />
            <Bar dataKey="value" fill="var(--chart-1)" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );

  useEffect(() => {
    if (!activeSelection) {
      setActiveView('map-default');
      return;
    }
    if (
      activeView === 'map-default' ||
      (activeView === 'heatmap-origin' && availability.originHeat) ||
      (activeView === 'heatmap-destination' && availability.destinationHeat) ||
      (activeView === 'departure-bins' && availability.departureBins) ||
      (activeView === 'arrival-bins' && availability.arrivalBins) ||
      (activeView === 'travel-time-bins' && availability.travelTimeBins) ||
      (activeView === 'top-origins' && availability.topOrigins) ||
      (activeView === 'flow-balance' && availability.flowBalance)
    ) {
      return;
    }
    setActiveView('map-default');
  }, [activeSelection, activeView, availability]);

  useEffect(() => {
    if (selectedCountyGeoid) {
      setActiveView('map-default');
    }
  }, [selectedCountyGeoid]);

  return (
    <div className="flex-1 flex min-h-0 overflow-hidden relative gap-4 p-4">
      <SidebarShell
        title="MoveOD Analysis"
        subtitle={
          activeSelection
            ? `${activeSelection.state_name ?? activeSelection.state_fips} • ${
                activeSelection.county_name ?? activeSelection.county_fips
              }`
            : 'Select a state and county'
        }
        footer={
          <button
            type="button"
            onClick={handleAnalyze}
            disabled={analyzing || !selectedStateFips || !selectedCountyGeoid}
            className="btn btn-primary w-full"
          >
            {analyzing ? 'Analyzing…' : 'Analyze'}
          </button>
        }
      >
        <div className="panel space-y-3">
          <div className="panel-title">Geography</div>
          <div className="control">
            <label className="control-label">State</label>
            <select
              value={selectedStateFips}
              onChange={(e) => {
                setSelectedStateFips(e.target.value);
                setSelectedCountyGeoid('');
              }}
              className="control-select"
            >
              <option value="">Select state</option>
              {states.map((state) => (
                <option key={state.state_fips} value={state.state_fips}>
                  {state.state_name ?? state.state_fips}
                </option>
              ))}
            </select>
          </div>
          <div className="control">
            <label className="control-label">County</label>
            <select
              value={selectedCountyGeoid}
              onChange={(e) => setSelectedCountyGeoid(e.target.value)}
              className="control-select"
              disabled={!selectedStateFips}
            >
              <option value="">Select county</option>
              {counties.map((county) => (
                <option key={county.county_geoid} value={county.county_geoid}>
                  {county.county_name ?? county.county_fips}
                </option>
              ))}
            </select>
          </div>
        </div>

        {jobId && <div className="control-hint">Job ID: {jobId}</div>}

        <div className="panel space-y-2">
          <div className="panel-title">Views</div>
          {views.map((view) => {
            const availabilityMap: Record<ViewId, boolean> = {
              'map-default': true,
              'heatmap-origin': availability.originHeat,
              'heatmap-destination': availability.destinationHeat,
              'departure-bins': availability.departureBins,
              'arrival-bins': availability.arrivalBins,
              'travel-time-bins': availability.travelTimeBins,
              'top-origins': availability.topOrigins,
              'flow-balance': availability.flowBalance
            };
            const isDisabled = !activeSelection || !availabilityMap[view.id];
            return (
              <button
                key={view.id}
                type="button"
                onClick={() => {
                  if (availabilityMap[view.id] && activeSelection) {
                    setActiveView(view.id);
                  }
                }}
                disabled={isDisabled}
                data-active={activeSelection && activeView === view.id}
                className="btn btn-outline w-full justify-between"
              >
                <span>{view.label}</span>
                {isDisabled ? <span className="tag">Pending</span> : <span className="tag">Ready</span>}
              </button>
            );
          })}
        </div>

        {activeSelection && (
          <div className="panel space-y-2">
            <div className="panel-title">Visibility</div>
            <div className="table-row">
              <span>Visible points</span>
              <span>
                {Math.round(originPoints.length * (pointVisibilityPercent / 100)) +
                  Math.round(destinationPoints.length * (pointVisibilityPercent / 100))}{' '}
                / {originPoints.length + destinationPoints.length}
              </span>
            </div>
            <input
              type="range"
              min={0}
              max={100}
              value={pointVisibilityPercent}
              onChange={(e) => setPointVisibilityPercent(Number(e.target.value))}
              className="w-full"
            />
            <div className="flex items-center justify-between text-xs text-muted">
              <span>0%</span>
              <span>{pointVisibilityPercent}%</span>
              <span>100%</span>
            </div>
          </div>
        )}

        <div className="control-hint">
          Other ideas: peak-period OD share, distance vs. time scatter, weekday vs. weekend split, top destinations.
        </div>
      </SidebarShell>

      <div className="map-panel">
        {!loading && !error && !activeSelection && (
          <div className="absolute inset-0 z-10 flex items-center justify-center p-6 pointer-events-none">
            <div className="empty-state">
              <div className="empty-art" aria-hidden="true">
                <div className="empty-ring" />
                <div className="empty-orbit" />
                <div className="empty-dot" />
              </div>
              <div className="empty-title">Ready for analysis</div>
              <div className="empty-text">
                Select a state and county to begin analysis.
              </div>
              <div className="empty-hint">Tip: pick a county with existing OD data for the fastest results.</div>
            </div>
          </div>
        )}
        {loading && (
          <div className="absolute inset-0 z-20 flex items-center justify-center overlay-scrim">
            <div className="floating-card flex items-center gap-2 text-sm">
              <span className="inline-flex h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-emerald-500" />
              Loading analysis…
            </div>
          </div>
        )}
        {error && (
          <div className="absolute inset-0 z-20 flex items-center justify-center overlay-scrim">
            <div className="warning-banner">{error}</div>
          </div>
        )}
        {!loading && !error && activeSelection && activeView === 'heatmap-origin' && (
          <MoveODAnalysisMap baseMapStyle={baseMapStyle} heatPoints={originHeat} />
        )}
        {!loading && !error && activeSelection && activeView === 'heatmap-destination' && (
          <MoveODAnalysisMap baseMapStyle={baseMapStyle} heatPoints={destinationHeat} />
        )}
        {!loading && !error && activeSelection && activeView === 'map-default' && (
          <MoveODAnalysisMap
            baseMapStyle={baseMapStyle}
            heatPoints={[]}
            originPoints={showOriginPoints ? visibleOriginPoints : []}
            destinationPoints={showDestinationPoints ? visibleDestinationPoints : []}
          />
        )}
        {!loading && !error && activeSelection && activeView === 'departure-bins' && renderChart(departureBins, 'Departure Times')}
        {!loading && !error && activeSelection && activeView === 'arrival-bins' && renderChart(arrivalBins, 'Arrival Times')}
        {!loading && !error && activeSelection && activeView === 'travel-time-bins' && renderChart(travelTimeBins, 'Travel Times')}
        {!loading && !error && activeSelection && activeView === 'top-origins' && renderChart(topOrigins, 'Top Origins')}
        {!loading && !error && activeSelection && activeView === 'flow-balance' && renderChart(flowBalance, 'Flow Balance')}
      </div>
    </div>
  );
}
