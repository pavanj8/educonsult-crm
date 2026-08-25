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
import type { RazorpayCheckoutOptions } from '../types/plan'

interface RazorpayInstance {
  open: () => void
  close: () => void
}

declare global {
  var Razorpay: new (options: RazorpayCheckoutOptions) => RazorpayInstance
}

describe('usePlanUpgrade', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // Reset Razorpay mock and related state
    delete (window as any).Razorpay
    vi.clearAllMocks()
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
      razorpay_key_id: 'rzp_test_123',
    }

    vi.mocked(createUpgradeOrder).mockResolvedValue(mockOrderResponse)

    // Mock Razorpay constructor
    const mockOpen = vi.fn()
    const mockClose = vi.fn()

    class MockRazorpay {
      open = mockOpen
      close = mockClose
    }

    ;(window as any).Razorpay = MockRazorpay

    const onSuccess = vi.fn()
    const { result } = renderHook(() => usePlanUpgrade())

    await result.current.initiateCheckout('growth', onSuccess)

    expect(createUpgradeOrder).toHaveBeenCalledWith('growth')
    expect(mockOpen).toHaveBeenCalledTimes(1)
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
      razorpay_key_id: 'rzp_test_123',
    }

    vi.mocked(createUpgradeOrder).mockResolvedValue(mockOrderResponse)

    class MockRazorpayClass {
      open = vi.fn()
      close = vi.fn()
    }
    window.Razorpay = vi.fn((_options: any) => new MockRazorpayClass()) as any

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
      razorpay_key_id: 'rzp_test_123',
    }

    vi.mocked(createUpgradeOrder).mockResolvedValue(mockOrderResponse)

    class MockRazorpayClass {
      open = vi.fn()
      close = vi.fn()
    }
    window.Razorpay = vi.fn((_options: any) => new MockRazorpayClass()) as any

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
      razorpay_key_id: 'rzp_test_123',
    }

    vi.mocked(createUpgradeOrder).mockResolvedValue(mockOrderResponse)

    // Mock Razorpay with a spy on the handler
    let capturedHandler: ((response: any) => void) | undefined = undefined
    const mockRazorpayInstance = {
      open: vi.fn(),
      close: vi.fn(),
    }
    const mockRazorpayConstructor = vi.fn().mockImplementation((options: any) => {
      capturedHandler = options.handler
      return mockRazorpayInstance
    })
    ;(window as any).Razorpay = mockRazorpayConstructor

    const onSuccess = vi.fn()
    const { result } = renderHook(() => usePlanUpgrade())

    await result.current.initiateCheckout('growth', onSuccess)

    // Verify the constructor was called and handler was captured
    expect(mockRazorpayConstructor).toHaveBeenCalled()
    expect(capturedHandler).toBeDefined()

    // Now trigger the handler manually
    capturedHandler!({
      razorpay_payment_id: 'pay_123',
      razorpay_order_id: 'order_123',
      razorpay_signature: 'signature',
    })

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
      razorpay_key_id: 'rzp_test_123',
    }

    vi.mocked(createUpgradeOrder).mockResolvedValue(mockOrderResponse)

    // Mock Razorpay with a spy on the dismiss handler
    let capturedOnDismiss: (() => void) | undefined = undefined
    const mockRazorpayInstance = {
      open: vi.fn(),
      close: vi.fn(),
    }
    const mockRazorpayConstructor = vi.fn().mockImplementation((options: any) => {
      capturedOnDismiss = options.modal?.ondismiss
      return mockRazorpayInstance
    })
    ;(window as any).Razorpay = mockRazorpayConstructor

    const onCancel = vi.fn()
    const { result } = renderHook(() => usePlanUpgrade())

    await result.current.initiateCheckout('growth', undefined, onCancel)

    // Verify the constructor was called and dismiss handler was captured
    expect(mockRazorpayConstructor).toHaveBeenCalled()
    expect(capturedOnDismiss).toBeDefined()

    // Now trigger the dismiss handler manually
    capturedOnDismiss!()

    expect(onCancel).toHaveBeenCalled()
    expect(result.current.loading).toBe(false)
  })
})
