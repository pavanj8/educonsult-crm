import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as counselorApi from './counselor'

// Mock the client module
vi.mock('./client', () => ({
  apiFetch: vi.fn(),
}))

import { apiFetch } from './client'

const mockedApiFetch = apiFetch as ReturnType<typeof vi.fn>

describe('counselor API', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  describe('fetchCounselorQueue', () => {
    it('fetches queue without filters', async () => {
      const mockData = [
        {
          id: 1,
          student_name: 'Alice',
          stage: 'registered',
        },
      ]
      mockedApiFetch.mockResolvedValueOnce(mockData)

      const result = await counselorApi.fetchCounselorQueue()

      expect(mockedApiFetch).toHaveBeenCalledWith('/counselor/queue')
      expect(result).toEqual(mockData)
    })

    it('fetches queue with stage filter', async () => {
      mockedApiFetch.mockResolvedValueOnce([])

      await counselorApi.fetchCounselorQueue({ stage: 'counseling' })

      expect(mockedApiFetch).toHaveBeenCalledWith('/counselor/queue?stage=counseling')
    })

    it('fetches queue with search filter', async () => {
      mockedApiFetch.mockResolvedValueOnce([])

      await counselorApi.fetchCounselorQueue({ search: 'Alice' })

      expect(mockedApiFetch).toHaveBeenCalledWith('/counselor/queue?search=Alice')
    })

    it('fetches queue with both filters', async () => {
      mockedApiFetch.mockResolvedValueOnce([])

      await counselorApi.fetchCounselorQueue({ stage: 'counseling', search: 'Bob' })

      expect(mockedApiFetch).toHaveBeenCalledWith('/counselor/queue?stage=counseling&search=Bob')
    })
  })

  describe('fetchCounselorQueueCounts', () => {
    it('fetches queue counts', async () => {
      const mockCounts = { registered: 5, counseling: 3 }
      mockedApiFetch.mockResolvedValueOnce(mockCounts)

      const result = await counselorApi.fetchCounselorQueueCounts()

      expect(mockedApiFetch).toHaveBeenCalledWith('/counselor/queue/counts')
      expect(result).toEqual(mockCounts)
    })
  })
})
