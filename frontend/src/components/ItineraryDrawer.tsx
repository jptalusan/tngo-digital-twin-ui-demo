import { useEffect, useMemo, useState } from 'react';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from './ui/accordion';
import { ChevronDown, ChevronUp, X } from 'lucide-react';

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
  const [collapsed, setCollapsed] = useState(false);
  const [activeValue, setActiveValue] = useState<string | undefined>(undefined);
  const omitGeometry = (value: unknown) => {
    if (!value || typeof value !== 'object') return value;
    if (Array.isArray(value)) return value.map(omitGeometry);
    return Object.entries(value).reduce<Record<string, unknown>>((acc, [key, val]) => {
      if (key === 'geometry') return acc;
      acc[key] = omitGeometry(val);
      return acc;
    }, {});
  };
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

  if (!open) return null;

  return (
    <div className="h-full w-full border-l bg-white shadow-xl">
      <div className="flex h-full flex-col">
        <div className="flex items-center justify-between border-b px-4 py-3">
          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                setCollapsed((prev) => {
                  const next = !prev;
                  if (next) {
                    setActiveValue(undefined);
                  } else {
                    setActiveValue(defaultValue);
                  }
                  return next;
                });
              }}
              className="rounded-md p-2 text-gray-500 hover:bg-gray-100"
              title={collapsed ? 'Expand' : 'Collapse'}
            >
              {collapsed ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
            </button>
            <div>
              <div className="text-sm font-semibold">Itineraries</div>
              <div className="text-xs text-gray-500">
                {modeLabel ? `${modeLabel} plan` : 'Trip plan'}
              </div>
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

        <div className="flex-1 overflow-y-auto px-6 py-4">
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

                return (
                  <AccordionItem key={itineraryId} value={`itinerary-${index}`}>
                    <AccordionTrigger>
                      <div className="flex items-center gap-2">
                        <span>Itinerary {index + 1}</span>
                        {isBest && (
                          <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700">
                            Best
                          </span>
                        )}
                      </div>
                    </AccordionTrigger>
                    <AccordionContent>
                      <div className="space-y-4">
                        <div>
                          <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Legs</div>
                          <div className="mt-2 space-y-2">
                            {legs.length === 0 ? (
                              <div className="text-sm text-gray-500">No legs.</div>
                            ) : (
                              legs.map((leg, legIndex) => (
                                <button
                                  key={`${itineraryId}-leg-${legIndex}`}
                                  onClick={() => onSelectLeg?.(leg)}
                                  className="w-full rounded-md border border-gray-200 p-2 text-left transition-colors hover:border-violet-300 hover:bg-violet-50"
                                >
                                  <div className="text-xs font-medium text-gray-600">Leg {legIndex + 1}</div>
                                  <pre className="mt-2 whitespace-pre-wrap text-xs text-gray-700">
                                    {JSON.stringify(omitGeometry(leg), null, 2)}
                                  </pre>
                                </button>
                              ))
                            )}
                          </div>
                        </div>
                      </div>
                    </AccordionContent>
                  </AccordionItem>
                );
              })}
            </Accordion>
          )}
        </div>
      </div>
    </div>
  );
}
