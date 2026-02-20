import { useEffect, useMemo, useState } from 'react';
import { MoveODMap, MoveODStateSelection } from './MoveODMap';
import type { MoveODAnalysisSelection } from './MoveODAnalysisPage';
import {
  Feature,
  FeatureCollection,
  useCountiesByState,
  useCountiesGeometryByState,
  useCountiesList,
  useCountiesSearch,
  useCountyGeometry,
  useStatesGeometry,
  useStatesSearch,
  useSyntheticDemand
} from '../hooks/useMoveOD';

export type StateOption = {
  state_fips: string;
  state_name: string;
  state_abbr?: string;
};

export type CountyOption = {
  geoid: string;
  name: string;
  state_fips: string;
  county_fips?: string;
};

const parseStateOption = (item: any): StateOption | null => {
  if (!item) return null;
  const state_fips = String(item.state_fips ?? item.STATEFP ?? item.STATE ?? '').padStart(2, '0');
  const state_name = String(item.state_name ?? item.NAME ?? item.state ?? '').trim();
  const state_abbr = item.state_abbr ?? item.STUSPS ?? item.state_abbrv ?? item.abbr;
  if (!state_fips || !state_name) return null;
  return { state_fips, state_name, state_abbr };
};

const parseCountyOption = (item: any): CountyOption | null => {
  if (!item) return null;
  const geoid = String(item.geoid ?? item.GEOID ?? '').trim();
  const name = String(item.name ?? item.county_name ?? item.NAME ?? '').trim();
  const state_fips = String(item.state_fips ?? item.STATEFP ?? '').padStart(2, '0');
  const county_fips = item.county_fips ?? item.COUNTYFP ?? undefined;
  if (!geoid || !name || !state_fips) return null;
  return { geoid, name, state_fips, county_fips };
};

const formatStateLabel = (state: StateOption) =>
  state.state_abbr ? `${state.state_name} (${state.state_abbr})` : state.state_name;

const formatCountyLabel = (county: CountyOption) => county.name;

const formatDateInput = (value: Date | null) => {
  if (!value) return '';
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, '0');
  const day = String(value.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
};

const parseDateInput = (value: string) => {
  if (!value) return null;
  const parsed = new Date(`${value}T00:00:00`);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
};

const buildYearOptions = (start: number, end: number) => {
  const years: number[] = [];
  for (let year = end; year >= start; year -= 1) {
    years.push(year);
  }
  return years;
};

interface MoveODPageProps {
  baseMapStyle?: 'standard' | 'light';
  onAnalyze?: (selection: MoveODAnalysisSelection) => void;
}

export function MoveODPage({ baseMapStyle = 'light', onAnalyze }: MoveODPageProps) {
  const [selectedState, setSelectedState] = useState<StateOption | null>(null);
  const [selectedCounty, setSelectedCounty] = useState<CountyOption | null>(null);

  const [stateQuery, setStateQuery] = useState('');
  const [countyQuery, setCountyQuery] = useState('');

  const [stateDropdownOpen, setStateDropdownOpen] = useState(false);
  const [countyDropdownOpen, setCountyDropdownOpen] = useState(false);
  const [stateActiveIndex, setStateActiveIndex] = useState(-1);
  const [countyActiveIndex, setCountyActiveIndex] = useState(-1);

  const [highlightedStateFips, setHighlightedStateFips] = useState<string | null>(null);

  const [dateRange, setDateRange] = useState<{ start: Date | null; end: Date | null }>({
    start: null,
    end: null
  });
  const [lodesYear, setLodesYear] = useState<number | ''>('');
  const [tigerYear, setTigerYear] = useState<number | ''>('');
  const [inrixDataPath, setInrixDataPath] = useState('');
  const [inrixConversionPath, setInrixConversionPath] = useState('');
  const [useGlobalBuildingsFootprint, setUseGlobalBuildingsFootprint] = useState(false);
  const [outputPath, setOutputPath] = useState('');
  const [showExistingDemand, setShowExistingDemand] = useState(false);
  const [demandVisibilityPercent, setDemandVisibilityPercent] = useState(100);
  const [showStatesLayer, setShowStatesLayer] = useState(true);
  const [showCountiesLayer, setShowCountiesLayer] = useState(true);
  const [showGeometryFill, setShowGeometryFill] = useState(true);

  const [errorBanner, setErrorBanner] = useState<string | null>(null);

  const [stateQueryDebounced, setStateQueryDebounced] = useState('');
  const [countyQueryDebounced, setCountyQueryDebounced] = useState('');

  useEffect(() => {
    const handle = window.setTimeout(() => setStateQueryDebounced(stateQuery), 300);
    return () => window.clearTimeout(handle);
  }, [stateQuery]);

  useEffect(() => {
    const handle = window.setTimeout(() => setCountyQueryDebounced(countyQuery), 300);
    return () => window.clearTimeout(handle);
  }, [countyQuery]);

  const {
    data: statesGeoJSON,
    loading: loadingStatesGeometry,
    error: statesGeometryError
  } = useStatesGeometry();
  const loadCountiesBase = false;
  const {
    data: countiesBaseGeoJSON,
    loading: loadingCountiesBase,
    error: countiesBaseError
  } = useCountiesList(loadCountiesBase);

  const {
    data: rawStateOptions,
    loading: loadingStateSearch,
    error: stateSearchError
  } = useStatesSearch(stateQueryDebounced);

  const {
    data: countyOptionsByState,
    loading: loadingCountyList,
    error: countyListError
  } = useCountiesByState(selectedState?.state_fips ?? null);
  const {
    data: countiesByStateGeometry,
    loading: loadingCountyGeometryList,
    error: countyGeometryListError
  } = useCountiesGeometryByState(selectedState?.state_fips ?? null);

  const {
    data: countySearchResults,
    loading: loadingCountySearch,
    error: countySearchError
  } = useCountiesSearch(countyQueryDebounced, selectedState?.state_fips ?? null);

  const {
    data: selectedCountyGeoJSON,
    loading: loadingSelectedCountyGeometry,
    error: countyGeometryError
  } = useCountyGeometry(selectedCounty?.geoid ?? null);

  const syntheticCountyFips =
    selectedCounty?.county_fips ?? (selectedCounty?.geoid ? selectedCounty.geoid.slice(2) : null);
  const demandLimit = Number(import.meta.env.VITE_MOVEOD_SYNTHETIC_DEMAND_LIMIT ?? 2000);
  const {
    data: syntheticDemandItems,
    loading: loadingSyntheticDemand,
    error: syntheticDemandError
  } = useSyntheticDemand(
    selectedState?.state_fips ?? null,
    syntheticCountyFips ?? null,
    demandLimit,
    !!selectedState && !!syntheticCountyFips
  );

  const stateOptions = useMemo(() => {
    return rawStateOptions
      .map(parseStateOption)
      .filter(Boolean) as StateOption[];
  }, [rawStateOptions]);

  const fullCountyOptions = useMemo(() => {
    return countyOptionsByState
      .map(parseCountyOption)
      .filter(Boolean) as CountyOption[];
  }, [countyOptionsByState]);

  const countyOptions = useMemo(() => {
    if (countyQueryDebounced.trim().length >= 2) {
      return countySearchResults.map(parseCountyOption).filter(Boolean) as CountyOption[];
    }
    return fullCountyOptions;
  }, [countyQueryDebounced, countySearchResults, fullCountyOptions]);

  useEffect(() => {
    setStateActiveIndex(stateOptions.length > 0 ? 0 : -1);
  }, [stateOptions]);

  useEffect(() => {
    setCountyActiveIndex(countyOptions.length > 0 ? 0 : -1);
  }, [countyOptions]);

  useEffect(() => {
    setShowExistingDemand(false);
    setDemandVisibilityPercent(100);
  }, [selectedState?.state_fips, selectedCounty?.geoid]);

  useEffect(() => {
    if (stateActiveIndex < 0) return;
    const el = document.getElementById(`moveod-state-option-${stateActiveIndex}`);
    el?.scrollIntoView({ block: 'nearest' });
  }, [stateActiveIndex]);

  useEffect(() => {
    if (countyActiveIndex < 0) return;
    const el = document.getElementById(`moveod-county-option-${countyActiveIndex}`);
    el?.scrollIntoView({ block: 'nearest' });
  }, [countyActiveIndex]);

  const years = useMemo(() => buildYearOptions(2010, 2024), []);

  useEffect(() => {
    const nextError =
      statesGeometryError ||
      countiesBaseError ||
      stateSearchError ||
      countyListError ||
      countySearchError ||
      countyGeometryError ||
      syntheticDemandError ||
      countyGeometryListError;
    setErrorBanner(nextError ?? null);
  }, [
    statesGeometryError,
    countiesBaseError,
    stateSearchError,
    countyListError,
    countySearchError,
    countyGeometryError,
    syntheticDemandError,
    countyGeometryListError
  ]);

  const handleStateSelect = (state: StateOption) => {
    setSelectedState(state);
    setHighlightedStateFips(state.state_fips);
    setStateQuery(formatStateLabel(state));
    setStateDropdownOpen(false);
    setStateActiveIndex(-1);
    setSelectedCounty(null);
    setCountyQuery('');
  };

  const handleCountySelect = (county: CountyOption) => {
    setSelectedCounty(county);
    setCountyQuery(formatCountyLabel(county));
    setCountyDropdownOpen(false);
    setCountyActiveIndex(-1);
  };

  const handleMapStateClick = (selection: MoveODStateSelection) => {
    if (!selection?.state_fips) return;
    const match = stateOptions.find((state) => state.state_fips === selection.state_fips);
    const nextState: StateOption = match ?? {
      state_fips: selection.state_fips,
      state_name: selection.state_name ?? `State ${selection.state_fips}`,
      state_abbr: selection.state_abbr
    };
    handleStateSelect(nextState);
  };

  const handleMapCountyClick = (selection: { geoid: string; name?: string; state_fips?: string; county_fips?: string }) => {
    if (!selection?.geoid) return;
    const fallbackStateFips = selection.state_fips ?? selectedState?.state_fips ?? selection.geoid.slice(0, 2);
    const option: CountyOption = {
      geoid: selection.geoid,
      name: selection.name ?? `County ${selection.geoid}`,
      state_fips: fallbackStateFips,
      county_fips: selection.county_fips ?? selection.geoid.slice(2)
    };
    handleCountySelect(option);
  };

  const dateRangeValid =
    (!dateRange.start && !dateRange.end) ||
    (dateRange.start !== null && dateRange.end !== null);

  const generateEnabled =
    !!selectedState &&
    !!selectedCounty &&
    !!outputPath &&
    dateRange.start !== null &&
    dateRange.end !== null;

  const handleGenerate = () => {
    if (!selectedState || !selectedCounty) return;
    const payload = {
      state_fips: selectedState.state_fips,
      county_geoid: selectedCounty.geoid,
      date_start: dateRange.start?.toISOString() ?? null,
      date_end: dateRange.end?.toISOString() ?? null,
      lodes_year: lodesYear || null,
      tiger_year: tigerYear || null,
      inrix_data_path: inrixDataPath,
      inrix_conversion_path: inrixConversionPath,
      use_global_buildings_footprint: useGlobalBuildingsFootprint,
      output_path: outputPath
    };
    console.log('[moveod] generate payload', payload);
  };

  const showCountyLoading = loadingCountySearch || loadingCountyList;
  const analysisSelection: MoveODAnalysisSelection | null = useMemo(() => {
    if (!selectedState || !selectedCounty) return null;
    const countyFips = selectedCounty.county_fips ?? selectedCounty.geoid.slice(2);
    return {
      state_fips: selectedState.state_fips,
      state_name: selectedState.state_name,
      county_geoid: selectedCounty.geoid,
      county_name: selectedCounty.name,
      county_fips: countyFips
    };
  }, [selectedState, selectedCounty]);
  const hasExistingDemand = syntheticDemandItems.length > 0;
  const syntheticDemandPoints = useMemo(() => {
    if (!showExistingDemand || !hasExistingDemand) return [] as Array<[number, number]>;
    const points: Array<[number, number]> = [];
    syntheticDemandItems.forEach((item: any) => {
      const origin = item?.origin_location;
      if (origin?.type === 'Point' && Array.isArray(origin.coordinates)) {
        const [lon, lat] = origin.coordinates;
        if (Number.isFinite(lat) && Number.isFinite(lon)) {
          points.push([lat, lon]);
        }
      }
      const dest = item?.destination_location;
      if (dest?.type === 'Point' && Array.isArray(dest.coordinates)) {
        const [lon, lat] = dest.coordinates;
        if (Number.isFinite(lat) && Number.isFinite(lon)) {
          points.push([lat, lon]);
        }
      }
    });
    const clampedPercent = Math.min(100, Math.max(0, demandVisibilityPercent));
    const visibleCount = Math.round(points.length * (clampedPercent / 100));
    return points.slice(0, visibleCount);
  }, [showExistingDemand, hasExistingDemand, syntheticDemandItems, demandVisibilityPercent]);

  const syntheticOriginPoints = useMemo(() => {
    if (!showExistingDemand || !hasExistingDemand) return [] as Array<[number, number]>;
    const points: Array<[number, number]> = [];
    syntheticDemandItems.forEach((item: any) => {
      const origin = item?.origin_location;
      if (origin?.type === 'Point' && Array.isArray(origin.coordinates)) {
        const [lon, lat] = origin.coordinates;
        if (Number.isFinite(lat) && Number.isFinite(lon)) {
          points.push([lat, lon]);
        }
      }
    });
    const clampedPercent = Math.min(100, Math.max(0, demandVisibilityPercent));
    const visibleCount = Math.round(points.length * (clampedPercent / 100));
    return points.slice(0, visibleCount);
  }, [showExistingDemand, hasExistingDemand, syntheticDemandItems, demandVisibilityPercent]);

  const syntheticDestinationPoints = useMemo(() => {
    if (!showExistingDemand || !hasExistingDemand) return [] as Array<[number, number]>;
    const points: Array<[number, number]> = [];
    syntheticDemandItems.forEach((item: any) => {
      const dest = item?.destination_location;
      if (dest?.type === 'Point' && Array.isArray(dest.coordinates)) {
        const [lon, lat] = dest.coordinates;
        if (Number.isFinite(lat) && Number.isFinite(lon)) {
          points.push([lat, lon]);
        }
      }
    });
    const clampedPercent = Math.min(100, Math.max(0, demandVisibilityPercent));
    const visibleCount = Math.round(points.length * (clampedPercent / 100));
    return points.slice(0, visibleCount);
  }, [showExistingDemand, hasExistingDemand, syntheticDemandItems, demandVisibilityPercent]);
  const totalDemandPoints = useMemo(() => {
    if (!hasExistingDemand) return 0;
    let total = 0;
    syntheticDemandItems.forEach((item: any) => {
      if (item?.origin_location?.type === 'Point') total += 1;
      if (item?.destination_location?.type === 'Point') total += 1;
    });
    return total;
  }, [hasExistingDemand, syntheticDemandItems]);
  const visibleDemandPointsCount = syntheticOriginPoints.length + syntheticDestinationPoints.length;

  const statesLayer = showStatesLayer ? (statesGeoJSON as FeatureCollection | null) : null;
  const countiesLayer =
    selectedState && !selectedCounty && showCountiesLayer
      ? (countiesByStateGeometry as FeatureCollection | null)
      : null;
  const countyHighlight = selectedCountyGeoJSON as Feature | FeatureCollection | null;

  return (
    <div className="flex-1 flex min-h-0 overflow-hidden relative">
      <div className="w-[360px] max-w-[360px] min-w-[360px] border-r bg-white flex flex-col">
        <div className="px-4 py-3 border-b">
          <div className="text-lg font-semibold text-slate-800">MoveOD</div>
          <div className="text-xs text-slate-500">Configure data extraction for a state and county.</div>
        </div>
        <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
          {errorBanner && (
            <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
              {errorBanner}
            </div>
          )}

          <div className="space-y-2">
            <label className="text-xs font-semibold text-slate-600">State</label>
            <div className="relative">
              <input
                value={stateQuery}
                onChange={(e) => {
                  setStateQuery(e.target.value);
                  setSelectedState(null);
                  setSelectedCounty(null);
                  setHighlightedStateFips(null);
                }}
                onKeyDown={(event) => {
                  if (!stateDropdownOpen) setStateDropdownOpen(true);
                  if (event.key === 'ArrowDown') {
                    event.preventDefault();
                    setStateActiveIndex((prev) =>
                      Math.min(stateOptions.length - 1, prev + 1)
                    );
                  }
                  if (event.key === 'ArrowUp') {
                    event.preventDefault();
                    setStateActiveIndex((prev) => Math.max(0, prev - 1));
                  }
                  if (event.key === 'Enter') {
                    event.preventDefault();
                    const target = stateOptions[stateActiveIndex];
                    if (target) handleStateSelect(target);
                  }
                  if (event.key === 'Escape') {
                    setStateDropdownOpen(false);
                  }
                }}
                onFocus={() => setStateDropdownOpen(true)}
                onBlur={() => window.setTimeout(() => setStateDropdownOpen(false), 150)}
                placeholder="Search for a state"
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
              />
              {stateDropdownOpen && (
                <div className="absolute z-30 mt-1 w-full rounded-lg border border-slate-200 bg-white shadow-lg">
                  <div className="max-h-60 overflow-y-auto py-1">
                    {loadingStateSearch && (
                      <div className="px-3 py-2 text-xs text-slate-500">Loading states…</div>
                    )}
                    {!loadingStateSearch && stateOptions.length === 0 && stateQueryDebounced.trim().length >= 2 && (
                      <div className="px-3 py-2 text-xs text-slate-500">No matches</div>
                    )}
                    {!loadingStateSearch && stateOptions.length === 0 && stateQueryDebounced.trim().length < 2 && (
                      <div className="px-3 py-2 text-xs text-slate-500">Type at least 2 characters</div>
                    )}
                    {stateOptions.map((state, index) => (
                      <button
                        key={state.state_fips}
                        type="button"
                        id={`moveod-state-option-${index}`}
                        onMouseDown={(event) => {
                          event.preventDefault();
                          handleStateSelect(state);
                        }}
                        className={`w-full px-3 py-2 text-left text-sm hover:bg-slate-50 ${
                          index === stateActiveIndex ? 'bg-slate-100' : ''
                        }`}
                      >
                        {formatStateLabel(state)}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-xs font-semibold text-slate-600">County</label>
            <div className="relative">
              <input
                value={countyQuery}
                onChange={(e) => {
                  setCountyQuery(e.target.value);
                  setSelectedCounty(null);
                }}
                onKeyDown={(event) => {
                  if (!selectedState) return;
                  if (!countyDropdownOpen) setCountyDropdownOpen(true);
                  if (event.key === 'ArrowDown') {
                    event.preventDefault();
                    setCountyActiveIndex((prev) =>
                      Math.min(countyOptions.length - 1, prev + 1)
                    );
                  }
                  if (event.key === 'ArrowUp') {
                    event.preventDefault();
                    setCountyActiveIndex((prev) => Math.max(0, prev - 1));
                  }
                  if (event.key === 'Enter') {
                    event.preventDefault();
                    const target = countyOptions[countyActiveIndex];
                    if (target) handleCountySelect(target);
                  }
                  if (event.key === 'Escape') {
                    setCountyDropdownOpen(false);
                  }
                }}
                onFocus={() => setCountyDropdownOpen(true)}
                onBlur={() => window.setTimeout(() => setCountyDropdownOpen(false), 150)}
                placeholder={selectedState ? 'Search for a county' : 'Select a state first'}
                disabled={!selectedState}
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm disabled:bg-slate-100"
              />
              {countyDropdownOpen && selectedState && (
                <div className="absolute z-30 mt-1 w-full rounded-lg border border-slate-200 bg-white shadow-lg">
                  {countyQuery && (
                    <div className="flex items-center justify-between border-b border-slate-100 px-3 py-2 text-xs text-slate-500">
                      <span>Filtered results</span>
                      <button
                        type="button"
                        onMouseDown={(event) => {
                          event.preventDefault();
                          setCountyQuery('');
                        }}
                        className="text-xs font-medium text-slate-600 hover:text-slate-800"
                      >
                        Clear
                      </button>
                    </div>
                  )}
                  <div className="max-h-60 overflow-y-auto py-1">
                    {showCountyLoading && (
                      <div className="px-3 py-2 text-xs text-slate-500">Loading counties…</div>
                    )}
                    {!showCountyLoading && countyOptions.length === 0 && (
                      <div className="px-3 py-2 text-xs text-slate-500">No matches</div>
                    )}
                    {!showCountyLoading && countyOptions.map((county, index) => (
                      <button
                        key={county.geoid}
                        type="button"
                        id={`moveod-county-option-${index}`}
                        onMouseDown={(event) => {
                          event.preventDefault();
                          handleCountySelect(county);
                        }}
                        className={`w-full px-3 py-2 text-left text-sm hover:bg-slate-50 ${
                          index === countyActiveIndex ? 'bg-slate-100' : ''
                        }`}
                      >
                        {formatCountyLabel(county)}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-semibold text-slate-600">Start Date</label>
              <input
                type="date"
                value={formatDateInput(dateRange.start)}
                onChange={(e) => setDateRange((prev) => ({ ...prev, start: parseDateInput(e.target.value) }))}
                className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="text-xs font-semibold text-slate-600">End Date</label>
              <input
                type="date"
                value={formatDateInput(dateRange.end)}
                onChange={(e) => setDateRange((prev) => ({ ...prev, end: parseDateInput(e.target.value) }))}
                className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
              />
            </div>
          </div>
          {!dateRangeValid && (
            <div className="text-xs text-rose-600">Select both start and end dates.</div>
          )}

          <div>
            <label className="text-xs font-semibold text-slate-600">LODES Data Year</label>
            <select
              value={lodesYear}
              onChange={(e) => setLodesYear(e.target.value ? Number(e.target.value) : '')}
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
            >
              <option value="">Select year</option>
              {years.map((year) => (
                <option key={`lodes-${year}`} value={year}>
                  {year}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="text-xs font-semibold text-slate-600">TIGER Shapefile Year</label>
            <select
              value={tigerYear}
              onChange={(e) => setTigerYear(e.target.value ? Number(e.target.value) : '')}
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
            >
              <option value="">Select year</option>
              {years.map((year) => (
                <option key={`tiger-${year}`} value={year}>
                  {year}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="text-xs font-semibold text-slate-600">INRIX Data Path</label>
            <input
              value={inrixDataPath}
              onChange={(e) => setInrixDataPath(e.target.value)}
              placeholder="/data/inrix/raw"
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
            />
          </div>

          <div>
            <label className="text-xs font-semibold text-slate-600">INRIX Conversion Path</label>
            <input
              value={inrixConversionPath}
              onChange={(e) => setInrixConversionPath(e.target.value)}
              placeholder="/data/inrix/converted"
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
            />
          </div>

          <label className="flex items-center gap-2 text-xs text-slate-700">
            <input
              type="checkbox"
              checked={useGlobalBuildingsFootprint}
              onChange={(e) => setUseGlobalBuildingsFootprint(e.target.checked)}
              className="h-4 w-4 rounded border-slate-300"
            />
            Use Global Buildings Footprint
          </label>

          <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600 space-y-2">
            <div className="text-[11px] font-semibold text-slate-600">Map Layers</div>
            <label className="flex items-center gap-2 text-xs text-slate-700">
              <input
                type="checkbox"
                checked={showStatesLayer}
                onChange={(e) => setShowStatesLayer(e.target.checked)}
                className="h-4 w-4 rounded border-slate-300"
              />
              Show state geometries
            </label>
            <label className="flex items-center gap-2 text-xs text-slate-700">
              <input
                type="checkbox"
                checked={showCountiesLayer}
                onChange={(e) => setShowCountiesLayer(e.target.checked)}
                className="h-4 w-4 rounded border-slate-300"
              />
              Show county geometries
            </label>
            <label className="flex items-center gap-2 text-xs text-slate-700">
              <input
                type="checkbox"
                checked={showGeometryFill}
                onChange={(e) => setShowGeometryFill(e.target.checked)}
                className="h-4 w-4 rounded border-slate-300"
              />
              Fill polygons
            </label>
          </div>

          <label className="flex items-center gap-2 text-xs text-slate-700">
            <input
              type="checkbox"
              checked={showExistingDemand}
              onChange={(e) => setShowExistingDemand(e.target.checked)}
              disabled={!hasExistingDemand}
              className="h-4 w-4 rounded border-slate-300 disabled:opacity-50"
            />
            Show previously generated existing OD data?
          </label>
          {showExistingDemand && hasExistingDemand && (
            <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600 space-y-2">
              <div className="flex items-center justify-between">
                <span>Visible points</span>
                <span className="font-semibold text-slate-700">
                  {visibleDemandPointsCount} / {totalDemandPoints}
                </span>
              </div>
              <input
                type="range"
                min={0}
                max={100}
                value={demandVisibilityPercent}
                onChange={(e) => setDemandVisibilityPercent(Number(e.target.value))}
                className="w-full"
              />
              <div className="flex items-center justify-between text-[11px] text-slate-500">
                <span>0%</span>
                <span>{demandVisibilityPercent}%</span>
                <span>100%</span>
              </div>
              {analysisSelection && onAnalyze && (
                <button
                  type="button"
                  onClick={() => onAnalyze(analysisSelection)}
                  className="w-full rounded-md bg-blue-600 px-3 py-2 text-xs font-semibold text-white hover:bg-blue-700"
                >
                  Open Analysis
                </button>
              )}
            </div>
          )}
          {loadingSyntheticDemand && selectedState && selectedCounty && (
            <div className="text-xs text-slate-500">Checking existing OD data…</div>
          )}
          {!loadingSyntheticDemand && selectedState && selectedCounty && !hasExistingDemand && (
            <div className="text-xs text-slate-500">No existing OD data found.</div>
          )}

          <div>
            <label className="text-xs font-semibold text-slate-600">Output Path</label>
            <input
              value={outputPath}
              onChange={(e) => setOutputPath(e.target.value)}
              placeholder="/outputs/moveod"
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
            />
          </div>
        </div>
        <div className="border-t px-4 py-3">
          <button
            type="button"
            onClick={handleGenerate}
            disabled={!generateEnabled}
            className="w-full rounded-lg bg-emerald-600 px-3 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:bg-slate-300 disabled:cursor-not-allowed"
          >
            Generate
          </button>
          <div className="mt-2 text-xs text-slate-500">
            {selectedState && selectedCounty
              ? 'Ready to submit once required fields are filled.'
              : 'Select a state and county to enable generation.'}
          </div>
        </div>
      </div>

      <div className="flex-1 min-w-0 min-h-0 relative">
        <MoveODMap
          baseMapStyle={baseMapStyle}
          statesGeoJSON={statesLayer}
          countiesGeoJSON={countiesLayer}
          selectedCountyGeoJSON={countyHighlight}
          highlightedStateFips={highlightedStateFips}
          syntheticOriginPoints={syntheticOriginPoints}
          syntheticDestinationPoints={syntheticDestinationPoints}
          showFill={showGeometryFill}
          onStateClick={handleMapStateClick}
          onCountyClick={handleMapCountyClick}
        />
        {loadingStatesGeometry && (
          <div className="absolute inset-0 z-20 flex items-center justify-center bg-white/70 backdrop-blur-sm">
            <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm text-slate-600 shadow-lg">
              <span className="inline-flex h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-blue-600" />
              Loading states…
            </div>
          </div>
        )}
        {(loadingCountiesBase || loadingSelectedCountyGeometry || loadingCountyGeometryList) && !loadingStatesGeometry && (
          <div className="absolute bottom-4 right-4 rounded-lg border border-slate-200 bg-white/90 px-3 py-2 text-xs text-slate-600 shadow">
            {loadingSelectedCountyGeometry
              ? 'Loading county geometry…'
              : loadingCountyGeometryList
              ? 'Loading counties layer…'
              : 'Loading counties layer…'}
          </div>
        )}
      </div>
    </div>
  );
}
