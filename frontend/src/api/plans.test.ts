/**
 * Tests for plans API client (E45, E46, E47; Journey J38, J39, J40).
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

import { fetchMyPlanAndUsage, createUpgradeOrder, fetchAllTenantsBillingStatus } from './plans'
import { apiFetch } from './client'
import type { PlanAndUsage, UpgradeOrderResponse, TenantBillingStatus } from '../types/plan'

// Mock the HTTP client
vi.mock('./client', () => ({
  apiFetch: vi.fn(),
}))

describe('plans API client', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('fetchMyPlanAndUsage', () => {
    it('should fetch plan and usage data successfully', async () => {
      const mockResponse: PlanAndUsage = {
        plan: {
          id: 1,
          code: 'growth',
          name: 'Growth',
          max_branches: 5,
          max_staff: 20,
          max_students: 100,
          is_active: true,
        },
        usage: {
          branches: 3,
          staff: 12,
          students: 67,
        },
      }

      vi.mocked(apiFetch).mockResolvedValue(mockResponse)

      const result = await fetchMyPlanAndUsage()

      expect(apiFetch).toHaveBeenCalledWith('/me/plan-usage')
      expect(result).toEqual(mockResponse)
    })

    it('should handle null plan (no plan assigned)', async () => {
      const mockResponse: PlanAndUsage = {
        plan: null,
        usage: {
          branches: 2,
          staff: 5,
          students: 30,
        },
      }

      vi.mocked(apiFetch).mockResolvedValue(mockResponse)

      const result = await fetchMyPlanAndUsage()

      expect(result.plan).toBeNull()
      expect(result.usage).toEqual({
        branches: 2,
        staff: 5,
        students: 30,
      })
    })

    it('should handle enterprise unlimited limits (null values)', async () => {
      const mockResponse: PlanAndUsage = {
        plan: {
          id: 3,
          code: 'enterprise',
          name: 'Enterprise',
          max_branches: null,
          max_staff: null,
          max_students: null,
          is_active: true,
        },
        usage: {
          branches: 10,
          staff: 50,
          students: 500,
        },
      }

      vi.mocked(apiFetch).mockResolvedValue(mockResponse)

      const result = await fetchMyPlanAndUsage()

      expect(result.plan?.max_branches).toBeNull()
      expect(result.plan?.max_staff).toBeNull()
      expect(result.plan?.max_students).toBeNull()
    })

    it('should throw error on network failure', async () => {
      vi.mocked(apiFetch).mockRejectedValue(new Error('Network error'))

      await expect(fetchMyPlanAndUsage()).rejects.toThrow('Network error')
    })

    it('should throw error on non-OK response', async () => {
      const mockError = new Error('Forbidden') as Error & { status: number }
      mockError.status = 403

      vi.mocked(apiFetch).mockRejectedValue(mockError)

      await expect(fetchMyPlanAndUsage()).rejects.toThrow('Forbidden')
    })
  })

  describe('createUpgradeOrder (E46; Journey J39)', () => {
    it('should create an upgrade order successfully', async () => {
      const mockResponse: UpgradeOrderResponse = {
        order_id: 'order_123abc',
        amount: 49900, // ₹499.00 in paisa
        currency: 'INR',
        plan_code: 'growth',
        plan_name: 'Growth',
        razorpay_key_id: 'rzp_test_123',
      }

      vi.mocked(apiFetch).mockResolvedValue(mockResponse)

      const result = await createUpgradeOrder('growth')

      expect(apiFetch).toHaveBeenCalledWith('/billing/create-upgrade-order', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plan_code: 'growth' }),
      })
      expect(result).toEqual(mockResponse)
    })

    it('should create an order for starter plan downgrade', async () => {
      const mockResponse: UpgradeOrderResponse = {
        order_id: 'order_456def',
        amount: 19900, // ₹199.00 in paisa
        currency: 'INR',
        plan_code: 'starter',
        plan_name: 'Starter',
        razorpay_key_id: 'rzp_test_123',
      }

      vi.mocked(apiFetch).mockResolvedValue(mockResponse)

      const result = await createUpgradeOrder('starter')

      expect(apiFetch).toHaveBeenCalledWith('/billing/create-upgrade-order', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plan_code: 'starter' }),
      })
      expect(result.plan_code).toBe('starter')
    })

    it('should create an order for enterprise plan upgrade', async () => {
      const mockResponse: UpgradeOrderResponse = {
        order_id: 'order_789ghi',
        amount: 99900, // ₹999.00 in paisa
        currency: 'INR',
        plan_code: 'enterprise',
        plan_name: 'Enterprise',
        razorpay_key_id: 'rzp_test_123',
      }

      vi.mocked(apiFetch).mockResolvedValue(mockResponse)

      const result = await createUpgradeOrder('enterprise')

      expect(result.order_id).toBe('order_789ghi')
      expect(result.amount).toBe(99900)
    })

    it('should handle 404 error for unknown plan code', async () => {
      const mockError = new Error('Plan not found') as Error & { status: number }
      mockError.status = 404

      vi.mocked(apiFetch).mockRejectedValue(mockError)

      await expect(createUpgradeOrder('growth')).rejects.toThrow('Plan not found')
    })

    it('should handle 409 error for inactive plan', async () => {
      const mockError = new Error('Plan is no longer active') as Error & { status: number }
      mockError.status = 409

      vi.mocked(apiFetch).mockRejectedValue(mockError)

      await expect(createUpgradeOrder('growth')).rejects.toThrow('Plan is no longer active')
    })

    it('should handle 503 error when Razorpay is unavailable', async () => {
      const mockError = new Error('Payment gateway is temporarily unavailable') as Error & { status: number }
      mockError.status = 503

      vi.mocked(apiFetch).mockRejectedValue(mockError)

      await expect(createUpgradeOrder('enterprise')).rejects.toThrow('Payment gateway is temporarily unavailable')
    })

    it('should handle network failure', async () => {
      vi.mocked(apiFetch).mockRejectedValue(new Error('Network error'))

      await expect(createUpgradeOrder('growth')).rejects.toThrow('Network error')
    })
  })

  describe('fetchAllTenantsBillingStatus (E47; Journey J40)', () => {
    it('should fetch all tenants billing status successfully', async () => {
      const mockResponse: TenantBillingStatus[] = [
        {
          tenant_id: 1,
          tenant_name: 'Tenant A',
          tenant_slug: 'tenant-a',
          plan: {
            code: 'starter',
            name: 'Starter Plan',
            max_branches: 1,
            max_staff: 5,
            max_students: 50,
            is_active: true,
          },
          branches_used: 1,
          staff_used: 2,
          students_used: 10,
          created_at: '2024-01-01T00:00:00Z',
          updated_at: '2024-01-01T00:00:00Z',
        },
        {
          tenant_id: 2,
          tenant_name: 'Tenant B',
          tenant_slug: 'tenant-b',
          plan: null,
          branches_used: 0,
          staff_used: 0,
          students_used: 0,
          created_at: '2024-01-02T00:00:00Z',
          updated_at: '2024-01-02T00:00:00Z',
        },
      ]

      vi.mocked(apiFetch).mockResolvedValue(mockResponse)

      const result = await fetchAllTenantsBillingStatus()

      expect(apiFetch).toHaveBeenCalledWith('/billing/tenant-status')
      expect(result).toEqual(mockResponse)
      expect(result).toHaveLength(2)
      expect(result[0].tenant_name).toBe('Tenant A')
      expect(result[1].plan).toBeNull()
    })

    it('should handle tenants with unlimited plan (null limits)', async () => {
      const mockResponse: TenantBillingStatus[] = [
        {
          tenant_id: 1,
          tenant_name: 'Enterprise Tenant',
          tenant_slug: 'enterprise-tenant',
          plan: {
            code: 'enterprise',
            name: 'Enterprise Plan',
            max_branches: null,
            max_staff: null,
            max_students: null,
            is_active: true,
          },
          branches_used: 100,
          staff_used: 500,
          students_used: 1000,
          created_at: '2024-01-01T00:00:00Z',
          updated_at: '2024-01-01T00:00:00Z',
        },
      ]

      vi.mocked(apiFetch).mockResolvedValue(mockResponse)

      const result = await fetchAllTenantsBillingStatus()

      expect(result[0].plan?.max_branches).toBeNull()
      expect(result[0].plan?.max_staff).toBeNull()
      expect(result[0].plan?.max_students).toBeNull()
    })

    it('should handle empty tenant list', async () => {
      const mockResponse: TenantBillingStatus[] = []

      vi.mocked(apiFetch).mockResolvedValue(mockResponse)

      const result = await fetchAllTenantsBillingStatus()

      expect(result).toEqual([])
      expect(apiFetch).toHaveBeenCalledWith('/billing/tenant-status')
    })

    it('should throw error on network failure', async () => {
      vi.mocked(apiFetch).mockRejectedValue(new Error('Network error'))

      await expect(fetchAllTenantsBillingStatus()).rejects.toThrow('Network error')
    })

    it('should throw error on 403 forbidden (non-super-admin)', async () => {
      const mockError = new Error('Forbidden') as Error & { status: number }
      mockError.status = 403

      vi.mocked(apiFetch).mockRejectedValue(mockError)

      await expect(fetchAllTenantsBillingStatus()).rejects.toThrow('Forbidden')
    })
  })
})
