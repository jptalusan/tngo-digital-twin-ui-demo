import { useEffect, useMemo, useState } from 'react';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from './ui/accordion';
import { X } from 'lucide-react';

type ItineraryLike = {
  itinerary_id?: string;
  legs?: unknown[];
  [key: string]: unknown;
};

interface ItineraryDrawerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  itineraries: ItineraryLike[];
  bestItineraryId?: string | null;
  selectedItineraryId?: string | null;
  onSelectItinerary?: (itinerary: ItineraryLike) => void;
  onSelectLeg?: (leg: unknown) => void;
  modeLabel?: string;
}

export function ItineraryDrawer({
  open,
  onOpenChange,
  itineraries,
  bestItineraryId,
  selectedItineraryId,
  onSelectItinerary,
  onSelectLeg,
  modeLabel
}: ItineraryDrawerProps) {
  const [activeValue, setActiveValue] = useState<string | undefined>(undefined);
  const [selectedLegKey, setSelectedLegKey] = useState<string | null>(null);

  const defaultValue = useMemo(() => {
    const index = bestItineraryId
      ? itineraries.findIndex((item) => item.itinerary_id === bestItineraryId)
      : -1;
    if (index >= 0) return `itinerary-${index}`;
    return itineraries.length > 0 ? 'itinerary-0' : undefined;
  }, [bestItineraryId, itineraries]);

  useEffect(() => {
    const index = selectedItineraryId
      ? itineraries.findIndex((item) => item.itinerary_id === selectedItineraryId)
      : -1;
    if (index >= 0) {
      setActiveValue(`itinerary-${index}`);
      return;
    }
    setActiveValue(defaultValue);
  }, [selectedItineraryId, itineraries, defaultValue]);

  const formatValue = (value: unknown) => {
    if (value === null || value === undefined) return '—';
    if (typeof value === 'number') return value.toFixed(2);
    if (typeof value === 'string') return value;
    return JSON.stringify(value);
  };
  const truncateAddress = (value: unknown) => {
    if (typeof value !== 'string') return formatValue(value);
    const parts = value.split(',').map((part) => part.trim()).filter(Boolean);
    if (parts.length <= 4) return parts.join(', ');
    return parts.slice(0, 4).join(', ');
  };

  const formatCoord = (v: number | null | undefined) =>
    v != null ? v.toFixed(3) : '—';

  const getScore = (itinerary: ItineraryLike) => {
    return (
      (itinerary as any)?.score ??
      (itinerary as any)?.metrics?.overall?.score ??
      null
    );
  };

  if (!open) return null;

  return (
    <div className="h-full w-full border-l bg-white shadow-xl flex flex-col overflow-hidden min-w-0">
      {/* Fixed header */}
      <div className="flex items-center justify-between border-b px-4 py-3 shrink-0">
        <div>
          <div className="text-sm font-semibold">Itineraries</div>
          <div className="text-xs text-gray-500">
            {modeLabel ? `${modeLabel} plan` : 'Trip plan'}
          </div>
        </div>
        <button
          onClick={() => onOpenChange(false)}
          className="rounded-md p-2 text-gray-500 hover:bg-gray-100"
          title="Close"
        >
          <X size={18} />
        </button>
      </div>

      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto px-4 py-3">
        {itineraries.length === 0 ? (
          <div className="text-sm text-gray-500">No itineraries returned.</div>
        ) : (
          <Accordion
            key={`${bestItineraryId ?? 'none'}-${itineraries.length}`}
            type="single"
            collapsible
            value={activeValue}
            onValueChange={(value) => {
              setActiveValue(value);
              setSelectedLegKey(null);
              const match = value?.match(/itinerary-(\d+)/);
              if (!match) return;
              const idx = Number(match[1]);
              const itinerary = itineraries[idx];
              if (itinerary && onSelectItinerary) {
                onSelectItinerary(itinerary);
              }
            }}
          >
            {itineraries.map((itinerary, index) => {
              const itineraryId = itinerary.itinerary_id ?? `itinerary-${index + 1}`;
              const isBest = bestItineraryId && itinerary.itinerary_id === bestItineraryId;
              const legs = Array.isArray(itinerary.legs) ? itinerary.legs : [];
              const score = getScore(itinerary);

              return (
                <AccordionItem key={itineraryId} value={`itinerary-${index}`}>
                  <AccordionTrigger>
                    <div className="flex flex-col gap-1 w-full pr-2">
                      <div className="flex items-center gap-2">
                        <span className="font-medium">Itinerary {index + 1}</span>
                        {isBest && (
                          <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700">
                            Best
                          </span>
                        )}
                      </div>
                      {score && (
                        <div className="text-xs text-gray-500">
                          Score: {formatValue(score.score)} · {formatValue(score.total_minutes)} min · {formatValue(score.walk_meters)} m walk
                        </div>
                      )}
                    </div>
                  </AccordionTrigger>
                  <AccordionContent>
                    <div className="space-y-2">
                      {legs.length === 0 ? (
                        <div className="text-sm text-gray-500">No legs.</div>
                      ) : (
                        legs.map((leg, legIndex) => {
                          const legKey = `${itineraryId}-leg-${legIndex}`;
                          const isHighlighted = selectedLegKey === legKey;

                          return (
                            <button
                              key={legKey}
                              onClick={() => {
                                setSelectedLegKey(isHighlighted ? null : legKey);
                                if (isHighlighted) {
                                  onSelectLeg?.(null);
                                } else {
                                  onSelectLeg?.(leg);
                                }
                              }}
                              className={`w-full rounded-lg border p-3 text-left transition-colors ${
                                isHighlighted
                                  ? 'border-blue-500 bg-blue-50 ring-2 ring-blue-300'
                                  : 'border-gray-200 hover:border-blue-300 hover:bg-blue-50'
                              }`}
                            >
                              <div className="flex items-center justify-between">
                                <div className="text-sm font-semibold text-gray-800">
                                  Leg {legIndex + 1} · {formatValue((leg as any)?.mode)}
                                </div>
                              </div>
                              <div className="mt-2 space-y-1.5 text-xs text-gray-600">
                                <div>
                                  <div className="uppercase tracking-wide text-[10px] text-gray-400">From</div>
                                  <div className="text-gray-700 truncate">
                                    {truncateAddress((leg as any)?.from_address ?? (leg as any)?.from_stop_id ?? '—')}
                                  </div>
                                  {(leg as any)?.from_coords && (
                                    <div className="text-[10px] text-gray-400">
                                      {formatCoord((leg as any).from_coords.lat)}, {formatCoord((leg as any).from_coords.lon)}
                                    </div>
                                  )}
                                </div>
                                <div>
                                  <div className="uppercase tracking-wide text-[10px] text-gray-400">To</div>
                                  <div className="text-gray-700 truncate">
                                    {truncateAddress((leg as any)?.to_address ?? (leg as any)?.to_stop_id ?? '—')}
                                  </div>
                                  {(leg as any)?.to_coords && (
                                    <div className="text-[10px] text-gray-400">
                                      {formatCoord((leg as any).to_coords.lat)}, {formatCoord((leg as any).to_coords.lon)}
                                    </div>
                                  )}
                                </div>
                                <div className="grid grid-cols-2 gap-2 pt-1">
                                  <div>
                                    <div className="uppercase tracking-wide text-[10px] text-gray-400">Distance</div>
                                    <div className="text-gray-700">
                                      {formatValue((leg as any)?.distance_m)} m
                                    </div>
                                  </div>
                                  <div>
                                    <div className="uppercase tracking-wide text-[10px] text-gray-400">Duration</div>
                                    <div className="text-gray-700">
                                      {formatValue((leg as any)?.duration_s)} s
                                    </div>
                                  </div>
                                </div>
                              </div>
                            </button>
                          );
                        })
                      )}
                    </div>
                  </AccordionContent>
                </AccordionItem>
              );
            })}
          </Accordion>
        )}
      </div>
    </div>
  );
}
