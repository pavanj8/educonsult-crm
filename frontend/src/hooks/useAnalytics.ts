/**
 * React hook for analytics data (E41; Journey J34).
 *
 * Provides conversion funnel data with optional date range filtering.
 */

import { useState, useEffect } from 'react'

import { fetchConversionFunnel } from '../api/analytics'
import type {
  AnalyticsParams,
  ConversionFunnelResponse,
  DateRange,
} from '../types/analytics'
import { isApiError } from '../api/client'

export function useAnalytics(dateRange?: DateRange) {
  const [data, setData] = useState<ConversionFunnelResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const reload = () => {
    setLoading(true)
    setError(null)

    const params: AnalyticsParams = {}
    if (dateRange?.startDate) {
      params.start_date = dateRange.startDate
    }
    if (dateRange?.endDate) {
      params.end_date = dateRange.endDate
    }

    fetchConversionFunnel(params)
      .then((responseData) => {
        setData(responseData)
        setLoading(false)
      })
      .catch((err) => {
        if (isApiError(err)) {
          setError(err.message)
        } else {
          setError('Failed to load analytics data')
        }
        setLoading(false)
      })
  }

  useEffect(() => {
    reload()
  }, [dateRange?.startDate, dateRange?.endDate])

  return { data, loading, error, reload }
}
