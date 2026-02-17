import { MapPin, Navigation } from 'lucide-react';
import { useEffect, useRef } from 'react';

interface MapContextMenuProps {
  x: number;
  y: number;
  onSetOrigin: () => void;
  onSetDestination: () => void;
  onClose: () => void;
}

export function MapContextMenu({ x, y, onSetOrigin, onSetDestination, onClose }: MapContextMenuProps) {
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        onClose();
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [onClose]);

  return (
    <div
      ref={menuRef}
      className="fixed bg-white rounded-lg shadow-lg border py-2 z-[2000]"
      style={{ left: x, top: y }}
    >
      <button
        onClick={() => {
          onSetOrigin();
          onClose();
        }}
        className="w-full px-4 py-2 text-left hover:bg-gray-100 flex items-center gap-2"
      >
        <MapPin size={16} className="text-green-600" />
        <span>Set as Origin</span>
      </button>
      <button
        onClick={() => {
          onSetDestination();
          onClose();
        }}
        className="w-full px-4 py-2 text-left hover:bg-gray-100 flex items-center gap-2"
      >
        <Navigation size={16} className="text-red-600" />
        <span>Set as Destination</span>
      </button>
    </div>
  );
}
