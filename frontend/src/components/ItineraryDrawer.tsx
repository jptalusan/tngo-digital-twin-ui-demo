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
    <div className="h-full w-full side-panel flex flex-col overflow-hidden min-w-0">
      {/* Fixed header */}
      <div className="flex items-center justify-between border-b border-default px-4 py-3 shrink-0">
        <div>
          <div className="text-sm font-semibold">Itineraries</div>
          <div className="text-xs text-muted">
            {modeLabel ? `${modeLabel} plan` : 'Trip plan'}
          </div>
        </div>
        <button
          onClick={() => onOpenChange(false)}
          className="btn btn-ghost"
          title="Close"
        >
          <X size={18} />
        </button>
      </div>

      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto px-4 py-3">
        {itineraries.length === 0 ? (
          <div className="text-sm text-muted">No itineraries returned.</div>
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
                        {isBest && <span className="control-chip">Best</span>}
                      </div>
                      {score && (
                        <div className="text-xs text-muted">
                          Score: {formatValue(score.score)} · {formatValue(score.total_minutes)} min · {formatValue(score.walk_meters)} m walk
                        </div>
                      )}
                    </div>
                  </AccordionTrigger>
                  <AccordionContent>
                    <div className="space-y-2">
                      {legs.length === 0 ? (
                        <div className="text-sm text-muted">No legs.</div>
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
                              className="w-full text-left panel-item"
                              data-active={isHighlighted}
                            >
                              <div className="flex items-center justify-between">
                                <div className="text-sm font-semibold">
                                  Leg {legIndex + 1} · {formatValue((leg as any)?.mode)}
                                </div>
                              </div>
                              <div className="mt-2 space-y-1.5 text-xs text-muted">
                                <div>
                                  <div className="uppercase tracking-wide text-xs text-muted">From</div>
                                  <div className="truncate">
                                    {truncateAddress((leg as any)?.from_address ?? (leg as any)?.from_stop_id ?? '—')}
                                  </div>
                                  {(leg as any)?.from_coords && (
                                    <div className="text-xs text-muted">
                                      {formatCoord((leg as any).from_coords.lat)}, {formatCoord((leg as any).from_coords.lon)}
                                    </div>
                                  )}
                                </div>
                                <div>
                                  <div className="uppercase tracking-wide text-xs text-muted">To</div>
                                  <div className="truncate">
                                    {truncateAddress((leg as any)?.to_address ?? (leg as any)?.to_stop_id ?? '—')}
                                  </div>
                                  {(leg as any)?.to_coords && (
                                    <div className="text-xs text-muted">
                                      {formatCoord((leg as any).to_coords.lat)}, {formatCoord((leg as any).to_coords.lon)}
                                    </div>
                                  )}
                                </div>
                                <div className="grid grid-cols-2 gap-2 pt-1">
                                  <div>
                                    <div className="uppercase tracking-wide text-xs text-muted">Distance</div>
                                    <div>
                                      {formatValue((leg as any)?.distance_m)} m
                                    </div>
                                  </div>
                                  <div>
                                    <div className="uppercase tracking-wide text-xs text-muted">Duration</div>
                                    <div>
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
