/**
 * Export Button Component (E44; Journey J37).
 *
 * Reusable button for triggering CSV/Excel exports with loading states
 * and error handling. Triggers browser download of exported data.
 */

import { useState } from 'react'

/**
 * Props for the ExportButton component.
 */
export interface ExportButtonProps {
  /**
   * The API endpoint path to call for export (e.g., '/analytics/export/students').
   */
  endpoint: string

  /**
   * Export format: 'csv' or 'xlsx'.
   */
  format: 'csv' | 'xlsx'

  /**
   * Optional label for the button. Defaults to "Export {format.toUpperCase()}".
   */
  label?: string

  /**
   * Optional query parameters to include in the export request.
   * Example: { start_date: '2024-01-01', end_date: '2024-12-31' }
   */
  queryParams?: Record<string, string>

  /**
   * Optional CSS class name for custom styling.
   */
  className?: string

  /**
   * Optional test ID for testing.
   */
  'data-testid'?: string

  /**
   * Disabled state for the button.
   */
  disabled?: boolean
}

/**
 * Export button component that triggers file download.
 */
export function ExportButton({
  endpoint,
  format,
  label,
  queryParams,
  className = '',
  'data-testid': testId = 'export-button',
  disabled = false,
}: ExportButtonProps) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleClick = async () => {
    setError(null)
    setLoading(true)

    try {
      // Build query string
      const searchParams = new URLSearchParams()
      searchParams.set('format', format)

      if (queryParams) {
        Object.entries(queryParams).forEach(([key, value]) => {
          if (value) {
            searchParams.set(key, value)
          }
        })
      }

      const queryString = searchParams.toString()
      const url = `${endpoint}${queryString ? `?${queryString}` : ''}`

      // Use fetch directly to handle blob response
      const token = localStorage.getItem('access_token')
      const response = await fetch(`${import.meta.env.VITE_API_BASE_URL}${url}`, {
        method: 'GET',
        headers: {
          Authorization: token ? `Bearer ${token}` : '',
          Accept: format === 'csv' ? 'text/csv' : 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        },
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Export failed' }))
        throw new Error(errorData.detail || 'Export failed')
      }

      // Get filename from Content-Disposition header or generate one
      const contentDisposition = response.headers.get('Content-Disposition')
      let filename = `export.${format}`
      
      if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename="(.+)"/)
        if (filenameMatch) {
          filename = filenameMatch[1]
        }
      }

      // Download the blob
      const blob = await response.blob()
      const blobUrl = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = blobUrl
      link.download = filename
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      window.URL.revokeObjectURL(blobUrl)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Export failed')
      // Clear error after 5 seconds
      setTimeout(() => setError(null), 5000)
    } finally {
      setLoading(false)
    }
  }

  const defaultLabel = format === 'csv' ? 'Export CSV' : 'Export Excel'

  return (
    <div className="export-button-wrapper">
      <button
        type="button"
        onClick={handleClick}
        disabled={disabled || loading}
        className={`export-button ${className}`}
        data-testid={testId}
        aria-live="polite"
      >
        {loading ? `Exporting...` : label || defaultLabel}
      </button>
      {error && (
        <p role="alert" className="export-error" data-testid="export-error">
          {error}
        </p>
      )}
    </div>
  )
}
