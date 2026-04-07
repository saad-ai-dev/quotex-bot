import { useState, useEffect, useCallback } from 'react';
import { getSignals, Signal, SignalListResponse } from '../services/api';

export interface HistoryFilters {
  market_type: string;
  expiry_profile: string;
  outcome: string;
  min_confidence: number;
  page: number;
  per_page: number;
}

interface UseHistoryReturn {
  history: Signal[];
  total: number;
  loading: boolean;
  error: string | null;
  filters: HistoryFilters;
  setFilters: (filters: Partial<HistoryFilters>) => void;
  refresh: () => void;
  totalPages: number;
}

const DEFAULT_FILTERS: HistoryFilters = {
  market_type: 'All',
  expiry_profile: 'All',
  outcome: 'All',
  min_confidence: 0,
  page: 1,
  per_page: 25,
};

export function useHistory(): UseHistoryReturn {
  const [history, setHistory] = useState<Signal[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFiltersState] = useState<HistoryFilters>(DEFAULT_FILTERS);

  const fetchHistory = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const skip = (filters.page - 1) * filters.per_page;
      const params: Record<string, string | number | undefined> = {
        skip,
        limit: filters.per_page,
        directional_only: 1,  // Only show UP/DOWN signals in history
        executed_only: 1,
      };
      if (filters.market_type !== 'All') params.market_type = filters.market_type;
      if (filters.expiry_profile !== 'All') params.expiry_profile = filters.expiry_profile;
      if (filters.outcome !== 'All') params.outcome = filters.outcome;

      // Use getSignals which calls /api/signals/ (the working endpoint)
      const data: SignalListResponse = await getSignals(params);
      setHistory(data.signals || []);
      setTotal(data.total || 0);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to load history';
      setError(msg);
      setHistory([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => { fetchHistory(); }, [fetchHistory]);

  const setFilters = useCallback((partial: Partial<HistoryFilters>) => {
    setFiltersState((prev) => {
      const next = { ...prev, ...partial };
      if (!('page' in partial)) next.page = 1;
      return next;
    });
  }, []);

  const totalPages = Math.max(1, Math.ceil(total / filters.per_page));

  return { history, total, loading, error, filters, setFilters, refresh: fetchHistory, totalPages };
}
