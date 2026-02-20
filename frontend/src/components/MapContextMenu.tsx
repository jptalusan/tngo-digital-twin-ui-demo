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
      className="fixed floating-card py-2 z-[2000]"
      style={{ left: x, top: y }}
    >
      <button
        onClick={() => {
          onSetOrigin();
          onClose();
        }}
        className="btn btn-ghost w-full justify-start"
      >
        <MapPin size={16} style={{ color: 'var(--app-accent)' }} />
        <span>Set as Origin</span>
      </button>
      <button
        onClick={() => {
          onSetDestination();
          onClose();
        }}
        className="btn btn-ghost w-full justify-start"
      >
        <Navigation size={16} style={{ color: 'var(--app-highlight)' }} />
        <span>Set as Destination</span>
      </button>
    </div>
  );
}
