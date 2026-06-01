import { useState, useEffect, useCallback } from 'react'

export interface PollState<T> {
  data: T | null
  loading: boolean
  error: string | null
}

export function usePolling<T>(
  fetcher: () => Promise<T>,
  intervalMs: number,
  deps: unknown[] = []
): PollState<T> {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const stableFetcher = useCallback(fetcher, deps)

  useEffect(() => {
    let cancelled = false
    const poll = async () => {
      try {
        const result = await stableFetcher()
        if (!cancelled) {
          setData(result)
          setError(null)
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e))
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    poll()
    const id = setInterval(poll, intervalMs)
    return () => {
      cancelled = true
      clearInterval(id)
    }
  }, [stableFetcher, intervalMs])

  return { data, loading, error }
}
