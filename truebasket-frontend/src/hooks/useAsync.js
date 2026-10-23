import { useCallback, useEffect, useState } from "react";

/**
 * Runs an async loader with cancellation. `loader(signal)` is re-run when
 * `deps` change or `retry()` is called. Pass `enabled=false` to skip.
 */
export function useAsync(loader, deps, { enabled = true } = {}) {
  const [state, setState] = useState({ data: null, error: null, loading: enabled });
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    if (!enabled) {
      setState({ data: null, error: null, loading: false });
      return undefined;
    }
    const controller = new AbortController();
    setState((s) => ({ data: s.data, error: null, loading: true }));
    loader(controller.signal).then(
      (data) => !controller.signal.aborted && setState({ data, error: null, loading: false }),
      (error) => !controller.signal.aborted && error?.kind !== "cancelled" && setState({ data: null, error, loading: false })
    );
    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, nonce, enabled]);

  const retry = useCallback(() => setNonce((n) => n + 1), []);
  return { ...state, retry };
}
