import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { AuthProvider } from '../store/authStore'
import CounselorDashboardPage from './CounselorDashboardPage'

const mockCounselor = {
  id: 10,
  email: 'counselor@demo.test',
  role: 'counselor' as const,
  tenant_id: 1,
  branch_id: 1,
}

const mockBranchManager = {
  id: 20,
  email: 'manager@demo.test',
  role: 'branch_manager' as const,
  tenant_id: 1,
  branch_id: 1,
}

const mockQueueData = [
  {
    id: 1,
    tenant_id: 1,
    student_id: 100,
    assigned_counselor_id: 10,
    target_university_id: null,
    target_program_id: null,
    stage: 'registered' as const,
    stage_reason: null,
    enrollment_date: null,
    loan_opted_in: false,
    loan_status: null,
    loan_lender: null,
    loan_amount: null,
    created_at: '2026-01-15T10:00:00Z',
    updated_at: '2026-01-15T10:00:00Z',
    student_name: 'Alice Johnson',
    student_email: 'alice@example.test',
    student_phone: '+91-9876543210',
    student_role: 'student' as const,
  },
  {
    id: 2,
    tenant_id: 1,
    student_id: 101,
    assigned_counselor_id: 10,
    target_university_id: null,
    target_program_id: null,
    stage: 'counseling' as const,
    stage_reason: null,
    enrollment_date: null,
    loan_opted_in: false,
    loan_status: null,
    loan_lender: null,
    loan_amount: null,
    created_at: '2026-01-16T11:00:00Z',
    updated_at: '2026-01-16T11:00:00Z',
    student_name: 'Bob Smith',
    student_email: 'bob@example.test',
    student_phone: null,
    student_role: 'student' as const,
  },
]

const mockCounts = {
  registered: 1,
  counseling: 1,
}

// Mock the counselor API
vi.mock('../api/counselor', () => ({
  fetchCounselorQueue: vi.fn(),
  fetchCounselorQueueCounts: vi.fn(),
}))

// Import after mocking
import { fetchCounselorQueue, fetchCounselorQueueCounts } from '../api/counselor'

const mockFetchQueue = fetchCounselorQueue as ReturnType<typeof vi.fn>
const mockFetchCounts = fetchCounselorQueueCounts as ReturnType<typeof vi.fn>

function createFetchMock(handlers: {
  user: typeof mockCounselor | typeof mockBranchManager
}) {
  return vi.fn(async (url: RequestInfo | URL) => {
    const path = String(url)

    if (path.includes('/auth/me')) {
      return {
        ok: true,
        status: 200,
        json: async () => handlers.user,
      }
    }

    throw new Error(`Unhandled fetch: ${path}`)
  }) as unknown as typeof fetch
}

function renderPage() {
  return render(
    <AuthProvider>
      <CounselorDashboardPage />
    </AuthProvider>,
  )
}

describe('CounselorDashboardPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.setItem('access_token', 'test-token')
    
    // Setup default API mocks
    mockFetchQueue.mockResolvedValue([])
    mockFetchCounts.mockResolvedValue({})
    
    // Mock the global fetch for auth
    globalThis.fetch = createFetchMock({ user: mockCounselor })
  })

  it('renders the counselor dashboard header', async () => {
    renderPage()

    await waitFor(() => {
      expect(screen.getByText('My Student Queue')).toBeInTheDocument()
    })

    expect(screen.getByText(/Manage your assigned students/i)).toBeInTheDocument()
  })

  it('displays applications in the queue table', async () => {
    mockFetchQueue.mockResolvedValueOnce(mockQueueData)
    mockFetchCounts.mockResolvedValueOnce(mockCounts)

    renderPage()

    await waitFor(() => {
      expect(screen.getByTestId('queue-table')).toBeInTheDocument()
    })

    expect(screen.getByText('Alice Johnson')).toBeInTheDocument()
    expect(screen.getByText('alice@example.test')).toBeInTheDocument()
    expect(screen.getByText('Bob Smith')).toBeInTheDocument()
    expect(screen.getByText('bob@example.test')).toBeInTheDocument()
  })

  it('shows student phone or dash when phone is null', async () => {
    mockFetchQueue.mockResolvedValueOnce(mockQueueData)
    mockFetchCounts.mockResolvedValueOnce(mockCounts)

    renderPage()

    await waitFor(() => {
      expect(screen.getByTestId('queue-table')).toBeInTheDocument()
    })

    // Alice has a phone number
    expect(screen.getByText('+91-9876543210')).toBeInTheDocument()
    // Bob has no phone (dash)
    expect(screen.getAllByText('-').length).toBeGreaterThan(0)
  })

  it('displays stage badges with counts', async () => {
    mockFetchQueue.mockResolvedValueOnce(mockQueueData)
    mockFetchCounts.mockResolvedValueOnce(mockCounts)

    renderPage()

    await waitFor(() => {
      expect(screen.getByTestId('total-count')).toBeInTheDocument()
    })

    expect(screen.getByTestId('total-count')).toHaveTextContent('2')
    expect(screen.getByTestId('stage-badge-registered')).toBeInTheDocument()
    expect(screen.getByTestId('stage-badge-counseling')).toBeInTheDocument()
  })

  it('shows loading state synchronously before data loads', async () => {
    // Use a promise that never resolves to simulate loading
    const pendingPromise = new Promise<never>(() => {})
    
    mockFetchQueue.mockImplementation(() => pendingPromise)
    mockFetchCounts.mockResolvedValueOnce({})

    renderPage()

    // Loading state should appear immediately before any async resolution
    expect(screen.queryByTestId('queue-loading')).toBeInTheDocument()
    expect(screen.queryByTestId('queue-table')).not.toBeInTheDocument()
  })

  it('shows empty state when no applications assigned', async () => {
    mockFetchQueue.mockResolvedValueOnce([])
    mockFetchCounts.mockResolvedValueOnce({})

    renderPage()

    await waitFor(() => {
      expect(screen.getByTestId('queue-empty')).toBeInTheDocument()
    })

    expect(screen.getByTestId('queue-empty')).toHaveTextContent('No applications assigned to you yet.')
  })

  it('shows error state and retry button when fetch fails', async () => {
    mockFetchQueue.mockRejectedValueOnce(new Error('Internal server error'))
    mockFetchCounts.mockResolvedValueOnce({})

    renderPage()

    await waitFor(() => {
      expect(screen.getByTestId('queue-error')).toBeInTheDocument()
    })

    expect(screen.getByTestId('queue-error')).toHaveTextContent('Internal server error')
    expect(screen.getByTestId('retry-button')).toBeInTheDocument()
  })

  it('filters queue by stage when stage filter changes and renders filtered results', async () => {
    // First call returns all data, second call returns filtered data
    mockFetchQueue
      .mockResolvedValueOnce(mockQueueData) // Initial load with all data
      .mockResolvedValueOnce([mockQueueData[0]]) // Filtered to 'registered' stage only
    mockFetchCounts.mockResolvedValue({ registered: 1, counseling: 1 })

    renderPage()

    // Wait for initial data to load
    await waitFor(() => {
      expect(screen.getByTestId('stage-filter')).toBeInTheDocument()
    })

    // Both students should be visible initially
    expect(screen.getByText('Alice Johnson')).toBeInTheDocument()
    expect(screen.getByText('Bob Smith')).toBeInTheDocument()

    // Change the stage filter to 'registered'
    const stageSelect = screen.getByTestId('stage-filter')
    await userEvent.selectOptions(stageSelect, 'registered')

    // Verify the API was called with the stage filter
    await waitFor(() => {
      expect(mockFetchQueue).toHaveBeenCalledWith({ stage: 'registered' })
    })

    // Verify the rendered output reflects the filter:
    // Alice (registered stage) should be visible
    expect(screen.getByText('Alice Johnson')).toBeInTheDocument()
    // Bob (counseling stage) should NOT be visible after filtering
    expect(screen.queryByText('Bob Smith')).not.toBeInTheDocument()
  })

  it('filters queue by search when search is entered and renders filtered results', async () => {
    // Use mockImplementation to return filtered results for any search containing 'alice'
    // This handles multiple onChange events from userEvent.type
    mockFetchQueue.mockImplementation((filter?: { stage?: string; search?: string }) => {
      if (filter?.search && filter.search.toLowerCase().includes('alice')) {
        return Promise.resolve([mockQueueData[0]])
      }
      if (filter?.search && filter.search.toLowerCase().includes('bob')) {
        return Promise.resolve([mockQueueData[1]])
      }
      return Promise.resolve(mockQueueData)
    })
    mockFetchCounts.mockResolvedValue({ registered: 1, counseling: 1 })

    renderPage()

    // Wait for initial data to load
    await waitFor(() => {
      expect(screen.getByTestId('queue-search')).toBeInTheDocument()
    })

    // Both students should be visible initially
    expect(screen.getByText('Alice Johnson')).toBeInTheDocument()
    expect(screen.getByText('Bob Smith')).toBeInTheDocument()

    // Type in the search field to filter for 'Alice'
    await userEvent.type(screen.getByTestId('queue-search'), 'Alice')

    // Wait for the filter to be applied and UI to update
    await waitFor(() => {
      // Verify the API was eventually called with the search filter
      expect(mockFetchQueue).toHaveBeenCalledWith(
        expect.objectContaining({ search: expect.stringContaining('Alice') })
      )
    })

    // Verify the rendered output reflects the filter:
    // Alice should be visible
    expect(screen.getByText('Alice Johnson')).toBeInTheDocument()
    // Bob should NOT be visible after filtering
    expect(screen.queryByText('Bob Smith')).not.toBeInTheDocument()
  })

  it('shows empty state when filters return no results', async () => {
    mockFetchQueue.mockResolvedValueOnce([])
    mockFetchCounts.mockResolvedValueOnce({})

    renderPage()

    await waitFor(() => {
      expect(screen.getByTestId('queue-empty')).toBeInTheDocument()
    })
  })

  it('shows clear filters button when filters are active', async () => {
    mockFetchQueue.mockResolvedValueOnce(mockQueueData)
    mockFetchCounts.mockResolvedValueOnce(mockCounts)

    renderPage()

    await waitFor(() => {
      expect(screen.getByTestId('queue-search')).toBeInTheDocument()
    })

    // Apply a search filter
    await userEvent.type(screen.getByTestId('queue-search'), 'test')

    await waitFor(() => {
      expect(screen.getByTestId('clear-filters')).toBeInTheDocument()
    })
  })

  it('displays stage tags in the table with correct colors', async () => {
    mockFetchQueue.mockResolvedValueOnce(mockQueueData)
    mockFetchCounts.mockResolvedValueOnce(mockCounts)

    renderPage()

    await waitFor(() => {
      expect(screen.getByTestId('stage-tag-1')).toBeInTheDocument()
    })

    expect(screen.getByTestId('stage-tag-1')).toHaveTextContent('Registered')
    expect(screen.getByTestId('stage-tag-2')).toHaveTextContent('Counseling')
  })

  it('renders for branch manager role', async () => {
    globalThis.fetch = createFetchMock({ user: mockBranchManager })
    mockFetchQueue.mockResolvedValueOnce(mockQueueData)
    mockFetchCounts.mockResolvedValueOnce(mockCounts)

    renderPage()

    await waitFor(() => {
      expect(screen.getByText('My Student Queue')).toBeInTheDocument()
    })
  })

  it('shows date in localized format', async () => {
    mockFetchQueue.mockResolvedValueOnce(mockQueueData)
    mockFetchCounts.mockResolvedValueOnce(mockCounts)

    renderPage()

    await waitFor(() => {
      expect(screen.getByTestId('queue-table')).toBeInTheDocument()
    })

    // Check that dates are formatted in the table (Jan 15, 2026 format)
    expect(screen.getByText(/Jan 15, 2026/)).toBeInTheDocument()
    expect(screen.getByText(/Jan 16, 2026/)).toBeInTheDocument()
  })

  it('clears search filter when clear filters button is clicked', async () => {
    // Return mockQueueData for both initial load and after clearing filters
    mockFetchQueue
      .mockResolvedValueOnce(mockQueueData) // Initial load
      .mockResolvedValueOnce(mockQueueData) // After clearing filters
    mockFetchCounts.mockResolvedValue(mockCounts)

    renderPage()

    await waitFor(() => {
      expect(screen.getByTestId('queue-search')).toBeInTheDocument()
    })

    // Apply search filter - use clear + paste for predictable behavior
    await userEvent.clear(screen.getByTestId('queue-search'))
    await userEvent.paste('Alice')

    await waitFor(() => {
      expect(screen.getByTestId('clear-filters')).toBeInTheDocument()
    })

    // Clear filters
    await userEvent.click(screen.getByTestId('clear-filters'))

    // Verify search input is cleared
    expect((screen.getByTestId('queue-search') as HTMLInputElement).value).toBe('')
  })

  it('renders stage tags with correct badge colors', async () => {
    mockFetchQueue.mockResolvedValueOnce(mockQueueData)
    mockFetchCounts.mockResolvedValueOnce(mockCounts)

    renderPage()

    await waitFor(() => {
      expect(screen.getByTestId('queue-table')).toBeInTheDocument()
    })

    // Check stage tags have the expected styling via CSS custom properties
    const registeredTag = screen.getByTestId('stage-tag-1')
    expect(registeredTag).toHaveStyle({ '--badge-color': '#6b7280' })

    const counselingTag = screen.getByTestId('stage-tag-2')
    expect(counselingTag).toHaveStyle({ '--badge-color': '#3b82f6' })
  })

  it('updates queue when stage badge is clicked', async () => {
    mockFetchQueue
      .mockResolvedValueOnce(mockQueueData) // Initial load with all data
      .mockResolvedValueOnce([mockQueueData[1]]) // Filtered to 'counseling' stage
    mockFetchCounts.mockResolvedValue({ registered: 1, counseling: 1 })

    renderPage()

    await waitFor(() => {
      expect(screen.getByTestId('stage-badge-counseling')).toBeInTheDocument()
    })

    // Both students should be visible initially
    expect(screen.getByText('Alice Johnson')).toBeInTheDocument()
    expect(screen.getByText('Bob Smith')).toBeInTheDocument()

    // Click on the counseling stage badge
    await userEvent.click(screen.getByTestId('stage-badge-counseling'))

    // Verify the API was called with the stage filter
    await waitFor(() => {
      expect(mockFetchQueue).toHaveBeenCalledWith({ stage: 'counseling' })
    })

    // Verify the rendered output reflects the filter:
    // Bob (counseling stage) should be visible
    expect(screen.getByText('Bob Smith')).toBeInTheDocument()
    // Alice (registered stage) should NOT be visible after filtering
    expect(screen.queryByText('Alice Johnson')).not.toBeInTheDocument()
  })
})
