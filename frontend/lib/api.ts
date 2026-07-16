"use client";

import { useEffect, useRef, useState } from "react";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function fetchJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return (await res.json()) as T;
}

export interface Poll<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
  updatedAt: Date | null;
}

/** Real-time polling hook: fetches `path` on mount and every `intervalMs`. */
export function usePoll<T>(path: string, intervalMs = 5000): Poll<T> {
  const [state, setState] = useState<Poll<T>>({
    data: null,
    error: null,
    loading: true,
    updatedAt: null,
  });
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    let alive = true;
    const run = async () => {
      try {
        const data = await fetchJSON<T>(path);
        if (alive) setState({ data, error: null, loading: false, updatedAt: new Date() });
      } catch (e) {
        if (alive)
          setState((s) => ({ ...s, error: (e as Error).message, loading: false }));
      }
    };
    run();
    timer.current = setInterval(run, intervalMs);
    return () => {
      alive = false;
      if (timer.current) clearInterval(timer.current);
    };
  }, [path, intervalMs]);

  return state;
}
