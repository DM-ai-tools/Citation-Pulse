"use client";

import { useEffect, useRef } from "react";

type MessageHandler = (ev: MessageEvent) => void;

/**
 * Native EventSource with simple auto-reconnect.
 * Pass `enabled: false` to tear down (e.g. scan completed).
 */
export function useEventSource(url: string | null, onMessage: MessageHandler, enabled = true) {
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;

  useEffect(() => {
    if (!url || !enabled) return;
    let es: EventSource | null = null;
    let cancelled = false;
    let attempt = 0;

    const connect = () => {
      if (cancelled) return;
      es = new EventSource(url);
      es.onmessage = (ev) => onMessageRef.current(ev);
      es.onerror = () => {
        es?.close();
        if (cancelled) return;
        attempt += 1;
        const delay = Math.min(30_000, 1000 * 2 ** Math.min(attempt, 5));
        setTimeout(connect, delay);
      };
    };

    connect();
    return () => {
      cancelled = true;
      es?.close();
    };
  }, [url, enabled]);
}
