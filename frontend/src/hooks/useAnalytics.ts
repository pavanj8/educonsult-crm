/**
 * React hook for analytics data (E41; Journey J34).
 *
 * Provides conversion funnel and registrations-over-time data
 * with optional date range filtering.
 */

import { useState, useEffect } from 'react'

import {
  fetchConversionFunnel,
  fetchRegistrationsOverTime,
} from '../api/analytics'
import type {
  AnalyticsParams,
  ConversionFunnelResponse,
  DateRange,
  RegistrationsOverTimeResponse,
} from '../types/analytics'
import { isApiError } from '../api/client'

export function useAnalytics(dateRange?: DateRange) {
  const [funnelData, setFunnelData] = useState<ConversionFunnelResponse | null>(
    null
  )
  const [registrationsData, setRegistrationsData] =
    useState<RegistrationsOverTimeResponse | null>(null)
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

    Promise.all([
      fetchConversionFunnel(params),
      fetchRegistrationsOverTime(params),
    ])
      .then(([funnelResponse, registrationsResponse]) => {
        setFunnelData(funnelResponse)
        setRegistrationsData(registrationsResponse)
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

  return { funnelData, registrationsData, loading, error, reload }
}
