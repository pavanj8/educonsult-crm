/**
 * Tests for usePlanUpgrade hook (E46; Journey J39).
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'

import { usePlanUpgrade } from './usePlanUpgrade'
import { createUpgradeOrder } from '../api/plans'

// Mock the API client
vi.mock('../api/plans', () => ({
  createUpgradeOrder: vi.fn(),
}))

// Mock Razorpay types (must match the hook's declaration)
// Import the actual types from the plan module
import type { RazorpayCheckoutOptions, RazorpayPaymentResponse } from '../types/plan'

interface RazorpayInstance {
  open: () => void
  close: () => void
}

declare global {
  interface Window {
    Razorpay?: new (options: RazorpayCheckoutOptions) => RazorpayInstance
  }
}

describe('usePlanUpgrade', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // Reset Razorpay mock
    delete (window as any).Razorpay
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('should initialize with loading false and no error', () => {
    const { result } = renderHook(() => usePlanUpgrade())

    expect(result.current.loading).toBe(false)
    expect(result.current.error).toBeNull()
  })

  it('should create order and call Razorpay open', async () => {
    const mockOrderResponse = {
      order_id: 'order_123',
      amount: 49900,
      currency: 'INR',
      plan_code: 'growth' as const,
      plan_name: 'Growth',
    }

    vi.mocked(createUpgradeOrder).mockResolvedValue(mockOrderResponse)

    // Mock Razorpay
    const mockRazorpayInstance = {
      open: vi.fn(),
      close: vi.fn(),
    }
    window.Razorpay = vi.fn(() => mockRazorpayInstance)

    const onSuccess = vi.fn()
    const { result } = renderHook(() => usePlanUpgrade())

    await result.current.initiateCheckout('growth', onSuccess)

    expect(createUpgradeOrder).toHaveBeenCalledWith('growth')
    expect(window.Razorpay).toHaveBeenCalled()
    expect(mockRazorpayInstance.open).toHaveBeenCalledTimes(1)
  })

  it('should handle API error during order creation', async () => {
    const apiError = new Error('Plan not found')
    vi.mocked(createUpgradeOrder).mockRejectedValue(apiError)

    const { result } = renderHook(() => usePlanUpgrade())

    await result.current.initiateCheckout('growth')

    await waitFor(() => {
      expect(result.current.error).toBe('Plan not found')
    })
    expect(result.current.loading).toBe(false)
  })

  it('should handle starter plan upgrade', async () => {
    const mockOrderResponse = {
      order_id: 'order_starter',
      amount: 19900,
      currency: 'INR',
      plan_code: 'starter' as const,
      plan_name: 'Starter',
    }

    vi.mocked(createUpgradeOrder).mockResolvedValue(mockOrderResponse)

    const mockRazorpayInstance = {
      open: vi.fn(),
      close: vi.fn(),
    }
    window.Razorpay = vi.fn(() => mockRazorpayInstance)

    const { result } = renderHook(() => usePlanUpgrade())

    await result.current.initiateCheckout('starter')

    expect(createUpgradeOrder).toHaveBeenCalledWith('starter')
  })

  it('should handle enterprise plan upgrade', async () => {
    const mockOrderResponse = {
      order_id: 'order_enterprise',
      amount: 99900,
      currency: 'INR',
      plan_code: 'enterprise' as const,
      plan_name: 'Enterprise',
    }

    vi.mocked(createUpgradeOrder).mockResolvedValue(mockOrderResponse)

    const mockRazorpayInstance = {
      open: vi.fn(),
      close: vi.fn(),
    }
    window.Razorpay = vi.fn(() => mockRazorpayInstance)

    const { result } = renderHook(() => usePlanUpgrade())

    await result.current.initiateCheckout('enterprise')

    expect(createUpgradeOrder).toHaveBeenCalledWith('enterprise')
  })

  it('should call onSuccess callback when payment succeeds', async () => {
    const mockOrderResponse = {
      order_id: 'order_123',
      amount: 49900,
      currency: 'INR',
      plan_code: 'growth' as const,
      plan_name: 'Growth',
    }

    vi.mocked(createUpgradeOrder).mockResolvedValue(mockOrderResponse)

    // Mock Razorpay with a spy on the handler
    let capturedHandler: ((response: any) => void) | null = null
    const mockRazorpayInstance = {
      open: vi.fn(),
      close: vi.fn(),
    }
    window.Razorpay = vi.fn((options: any) => {
      capturedHandler = options.handler
      return mockRazorpayInstance
    })

    const onSuccess = vi.fn()
    const { result } = renderHook(() => usePlanUpgrade())

    await result.current.initiateCheckout('growth', onSuccess)

    // Now trigger the handler manually
    expect(capturedHandler).not.toBeNull()
    if (capturedHandler) {
      capturedHandler({
        razorpay_payment_id: 'pay_123',
        razorpay_order_id: 'order_123',
        razorpay_signature: 'signature',
      })
    }

    expect(onSuccess).toHaveBeenCalled()
    expect(result.current.loading).toBe(false)
  })

  it('should call onCancel callback when modal is dismissed', async () => {
    const mockOrderResponse = {
      order_id: 'order_123',
      amount: 49900,
      currency: 'INR',
      plan_code: 'growth' as const,
      plan_name: 'Growth',
    }

    vi.mocked(createUpgradeOrder).mockResolvedValue(mockOrderResponse)

    // Mock Razorpay with a spy on the dismiss handler
    let capturedOnDismiss: (() => void) | null = null
    const mockRazorpayInstance = {
      open: vi.fn(),
      close: vi.fn(),
    }
    window.Razorpay = vi.fn((options: any) => {
      capturedOnDismiss = options.modal?.ondismiss || null
      return mockRazorpayInstance
    })

    const onCancel = vi.fn()
    const { result } = renderHook(() => usePlanUpgrade())

    await result.current.initiateCheckout('growth', undefined, onCancel)

    // Now trigger the dismiss handler manually
    expect(capturedOnDismiss).not.toBeNull()
    if (capturedOnDismiss) {
      capturedOnDismiss()
    }

    expect(onCancel).toHaveBeenCalled()
    expect(result.current.loading).toBe(false)
  })
})
