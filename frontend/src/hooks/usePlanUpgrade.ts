/**
 * Custom hook for plan upgrade/downgrade checkout (E46; Journey J39).
 *
 * This hook provides functionality to:
 * 1. Create a Razorpay order for plan upgrade/downgrade.
 * 2. Open the Razorpay checkout modal.
 * 3. Handle payment success/cancel callbacks.
 */

import { useCallback, useRef, useState } from 'react'

import { createUpgradeOrder } from '../api/plans'
import type { RazorpayCheckoutOptions, RazorpayPaymentResponse } from '../types/plan'

interface UsePlanUpgradeState {
  loading: boolean
  error: string | null
  initiateCheckout: (planCode: 'starter' | 'growth' | 'enterprise', onSuccess?: () => void, onCancel?: () => void) => Promise<void>
}

// Declare Razorpay type globally (loaded via external script)
declare global {
  interface Window {
    Razorpay: new (options: RazorpayCheckoutOptions) => {
      open: () => void
      close: () => void
    }
  }
}

/**
 * Hook to manage plan upgrade/downgrade checkout flow.
 *
 * This hook:
 * - Creates a Razorpay order via the backend API.
 * - Dynamically loads the Razorpay checkout script if not already loaded.
 * - Opens the Razorpay checkout modal with the order details.
 * - Handles payment success and cancel callbacks.
 *
 * @returns Object with loading state, error, and initiateCheckout function.
 */
export function usePlanUpgrade(): UsePlanUpgradeState {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const scriptLoadedRef = useRef(false)
  const loadingScriptRef = useRef(false)
  const scriptLoadPromiseRef = useRef<Promise<void> | null>(null)

  /**
   * Dynamically load the Razorpay checkout script.
   * This script is safe to call multiple times – it tracks load state.
   */
  const loadRazorpayScript = useCallback((): Promise<void> => {
    // If already loaded, return immediately
    if (scriptLoadedRef.current || typeof window.Razorpay !== 'undefined') {
      scriptLoadedRef.current = true
      return Promise.resolve()
    }

    // If already loading, return the existing promise
    if (loadingScriptRef.current && scriptLoadPromiseRef.current) {
      return scriptLoadPromiseRef.current
    }

    // Start loading
    loadingScriptRef.current = true
    scriptLoadPromiseRef.current = new Promise((resolve, reject) => {
      const script = document.createElement('script')
      script.src = 'https://checkout.razorpay.com/v1/checkout.js'
      script.async = true
      script.onload = () => {
        scriptLoadedRef.current = true
        loadingScriptRef.current = false
        resolve()
      }
      script.onerror = () => {
        loadingScriptRef.current = false
        reject(new Error('Failed to load Razorpay checkout script'))
      }
      document.body.appendChild(script)
    })

    return scriptLoadPromiseRef.current
  }, [])

  /**
   * Initiate the checkout flow for a plan upgrade/downgrade.
   *
   * This function:
   * 1. Creates a Razorpay order via the backend.
   * 2. Loads the Razorpay checkout script (if not already loaded).
   * 3. Opens the checkout modal with the order details.
   * 4. Invokes the onSuccess callback when payment succeeds.
   * 5. Invokes the onCancel callback when the user closes the modal.
   *
   * @param planCode - The target plan tier code (starter, growth, enterprise).
   * @param onSuccess - Optional callback invoked when payment succeeds.
   * @param onCancel - Optional callback invoked when the modal is closed.
   */
  const initiateCheckout = useCallback(
    async (
      planCode: 'starter' | 'growth' | 'enterprise',
      onSuccess?: () => void,
      onCancel?: () => void
    ): Promise<void> => {
      setLoading(true)
      setError(null)

      try {
        // Step 1: Create Razorpay order via backend
        const orderResponse = await createUpgradeOrder(planCode)

        // Step 2: Load Razorpay checkout script
        await loadRazorpayScript()

        // Step 3: Configure checkout options
        const options: RazorpayCheckoutOptions = {
          key: '', // Will be set by backend rendering or environment variable
          order_id: orderResponse.order_id,
          amount: orderResponse.amount,
          currency: orderResponse.currency,
          name: 'EduConsult CRM',
          handler: (_response: RazorpayPaymentResponse) => {
            // Payment succeeded – the webhook will handle plan change
            setLoading(false)
            onSuccess?.()
          },
          modal: {
            ondismiss: () => {
              // User closed the modal without paying
              setLoading(false)
              onCancel?.()
            },
          },
        }

        // Step 4: Open checkout
        const razorpay = new window.Razorpay(options)
        razorpay.open()
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to initiate checkout'
        setError(message)
        setLoading(false)
      }
    },
    [loadRazorpayScript]
  )

  return { loading, error, initiateCheckout }
}
