"use client";

import { useQuery } from "@tanstack/react-query";
import { Crosshair, Globe, MapPin, X } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Place } from "@/lib/types";

export const RADIUS_OPTIONS_KM = [5, 10, 25, 50, 100, 250, 500, 1000];

function useDebounced<T>(value: T, ms = 350): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return debounced;
}

interface Props {
  place: Place | null;
  radiusKm: number;
  onPlaceChange: (place: Place | null) => void;
  onRadiusChange: (km: number) => void;
}

/** Pick a search location (place search or browser geolocation) and a radius; empty means global. */
export function LocationPicker({ place, radiusKm, onPlaceChange, onRadiusChange }: Props) {
  const [term, setTerm] = useState("");
  const [open, setOpen] = useState(false);
  const [locating, setLocating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const debounced = useDebounced(term.trim());

  const results = useQuery({
    queryKey: ["geo-search", debounced],
    queryFn: () => api<Place[]>(`geo/search?q=${encodeURIComponent(debounced)}`),
    enabled: debounced.length >= 2 && !place,
    staleTime: 5 * 60_000,
  });

  function choose(p: Place) {
    onPlaceChange(p);
    setTerm("");
    setOpen(false);
    setError(null);
  }

  function useMyLocation() {
    if (!navigator.geolocation) {
      setError("Your browser does not support location access.");
      return;
    }
    setLocating(true);
    setError(null);
    navigator.geolocation.getCurrentPosition(
      async ({ coords }) => {
        try {
          choose(await api<Place>(`geo/reverse?lat=${coords.latitude}&lon=${coords.longitude}`));
        } catch (e) {
          setError((e as Error).message);
        } finally {
          setLocating(false);
        }
      },
      (err) => {
        setLocating(false);
        setError(err.code === err.PERMISSION_DENIED ? "Location permission denied." : "Could not get your location.");
      },
      { timeout: 10_000, maximumAge: 300_000 },
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-col gap-2 md:flex-row md:items-center">
        <div className="relative md:flex-1">
          {place ? (
            <div className="input flex items-center gap-2">
              <MapPin className="h-4 w-4 shrink-0 text-brand" />
              <span className="truncate">{place.label}</span>
              <button
                type="button"
                className="ml-auto text-slate-400 hover:text-white"
                onClick={() => onPlaceChange(null)}
                aria-label="Clear location"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          ) : (
            <>
              <Globe className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-500" />
              <input
                className="input pl-9"
                placeholder="Anywhere (global) - or search a city, region or country"
                value={term}
                onChange={(e) => {
                  setTerm(e.target.value);
                  setOpen(true);
                }}
                onFocus={() => setOpen(true)}
                onBlur={() => setTimeout(() => setOpen(false), 150)}
                maxLength={200}
              />
              {open && debounced.length >= 2 && (
                <ul className="absolute z-20 mt-1 max-h-64 w-full overflow-auto rounded-lg border border-slate-700 bg-slate-900 shadow-xl">
                  {results.isFetching && <li className="px-3 py-2 text-sm text-slate-500">Searching...</li>}
                  {results.error && <li className="px-3 py-2 text-sm text-rose-400">{results.error.message}</li>}
                  {results.data?.length === 0 && <li className="px-3 py-2 text-sm text-slate-500">No places found</li>}
                  {results.data?.map((p) => (
                    <li key={`${p.lat},${p.lon}`}>
                      <button
                        type="button"
                        className="flex w-full items-start gap-2 px-3 py-2 text-left text-sm hover:bg-slate-800"
                        onMouseDown={(e) => e.preventDefault()}
                        onClick={() => choose(p)}
                      >
                        <MapPin className="mt-0.5 h-4 w-4 shrink-0 text-slate-500" />
                        <span>{p.label}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
        </div>

        <button type="button" className="btn-ghost justify-center" onClick={useMyLocation} disabled={locating}>
          <Crosshair className="h-4 w-4" />
          {locating ? "Locating..." : "Use my location"}
        </button>

        <label className="flex items-center gap-2 text-sm text-slate-300">
          Radius
          <select
            className="input w-28"
            value={radiusKm}
            onChange={(e) => onRadiusChange(Number(e.target.value))}
            disabled={!place}
            title={place ? "Search radius around the selected location" : "Pick a location to set a radius"}
          >
            {RADIUS_OPTIONS_KM.map((km) => (
              <option key={km} value={km}>
                {km} km
              </option>
            ))}
          </select>
        </label>
      </div>
      {error && <p className="text-sm text-rose-400">{error}</p>}
      {place && (
        <p className="text-xs text-slate-500">
          Search volume, trends and SERP data are localised to this area; community sources are filtered by place name.
        </p>
      )}
    </div>
  );
}

export function geoLabel(geo: { label: string; radius_km: number } | null | undefined): string {
  return geo ? `${geo.label.split(",").slice(0, 2).join(",")} - ${geo.radius_km} km` : "Global";
}
