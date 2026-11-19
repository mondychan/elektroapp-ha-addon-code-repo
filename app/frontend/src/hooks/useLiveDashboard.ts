import { useEffect, useRef, useState } from "react";
import { elektroappApi } from "../api/elektroappApi";
import { LiveDashboardResponse } from "../types/elektroapp";

function isAbortError(err: unknown): boolean {
  const name = (err as { name?: string } | null)?.name;
  return name === "CanceledError" || name === "AbortError" || name === "ERR_CANCELED";
}

function payloadSignature(data: LiveDashboardResponse | null): string {
  if (!data) return "null";
  const prices = Array.isArray(data.prices) ? data.prices : [];
  let sum = 0;
  for (const item of prices) {
    sum += Number(item?.final) || 0;
  }
  // The battery block carries its own ``server_time``, which the backend
  // stamps on every build.  Keeping it here would make the signature differ at
  // 1 Hz even when no reading changed, re-rendering every chart once per second;
  // drop it and let the real readings drive the update.
  const battery = data.battery ? { ...data.battery } : null;
  if (battery) delete battery.server_time;
  return JSON.stringify({
    date: data.date,
    slot: data.current_slot,
    alerts: data.alerts,
    battery,
    prices: prices.length,
    sum: Math.round(sum * 1000) / 1000,
  });
}

interface UseLiveDashboardOptions {
  active: boolean;
  intervalMs?: number;
  onLoaded?: (data: LiveDashboardResponse) => void;
  onError?: (err: unknown) => void;
}

export const useLiveDashboard = ({
  active,
  intervalMs = 1000,
  onLoaded,
  onError,
}: UseLiveDashboardOptions) => {
  const [data, setData] = useState<LiveDashboardResponse | null>(null);
  const [lastSuccessAt, setLastSuccessAt] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [isPolling, setIsPolling] = useState(false);

  const loadedRef = useRef(onLoaded);
  const errorRef = useRef(onError);
  const signatureRef = useRef<string>("null");

  useEffect(() => {
    loadedRef.current = onLoaded;
    errorRef.current = onError;
  }, [onLoaded, onError]);

  useEffect(() => {
    if (!active) {
      setIsPolling(false);
      return undefined;
    }

    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;
    let controller: AbortController | null = null;

    const schedule = (delay: number) => {
      if (cancelled) return;
      timer = setTimeout(tick, Math.max(0, delay));
    };

    const tick = async () => {
      if (cancelled) return;
      controller = new AbortController();
      const startedAt = Date.now();
      try {
        const next = await elektroappApi.getLiveDashboard(controller.signal);
        if (cancelled) return;
        const signature = payloadSignature(next);
        if (signature !== signatureRef.current) {
          signatureRef.current = signature;
          setData(next);
          // Only advance the "updated" stamp when something actually changed;
          // otherwise this hook would re-render the whole dashboard once per
          // second for a clock that shows the same numbers.
          setLastSuccessAt(next.server_time || new Date().toISOString());
        }
        setError(null);
        loadedRef.current?.(next);
      } catch (err) {
        if (cancelled || isAbortError(err)) return;
        setError(err);
        errorRef.current?.(err);
      } finally {
        if (!cancelled) {
          setIsPolling(true);
          schedule(intervalMs - (Date.now() - startedAt));
        }
      }
    };

    tick();

    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
      if (controller) controller.abort();
      setIsPolling(false);
    };
  }, [active, intervalMs]);

  return { data, error, lastSuccessAt, isPolling };
};
