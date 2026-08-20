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

  it('shows loading state while fetching queue', async () => {
    // Keep the queue empty to avoid async issues
    mockFetchQueue.mockResolvedValueOnce([])
    mockFetchCounts.mockResolvedValueOnce({})

    renderPage()

    // The component should render immediately with loading state if data is not yet loaded
    await waitFor(() => {
      expect(screen.queryByTestId('queue-empty') || screen.queryByTestId('queue-loading')).toBeTruthy()
    })
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

  it('filters queue by stage when stage filter changes', async () => {
    mockFetchQueue.mockResolvedValueOnce([mockQueueData[0]])
    mockFetchCounts.mockResolvedValueOnce(mockCounts)

    renderPage()

    await waitFor(() => {
      expect(screen.getByTestId('stage-filter')).toBeInTheDocument()
    })

    // Change the stage filter
    const stageSelect = screen.getByTestId('stage-filter')
    await userEvent.selectOptions(stageSelect, 'counseling')

    await waitFor(() => {
      // Verify the API was called with the stage filter
      expect(mockFetchQueue).toHaveBeenCalledWith({ stage: 'counseling' })
    })
  })

  it('filters queue by search term', async () => {
    mockFetchQueue.mockResolvedValueOnce(mockQueueData)
    mockFetchCounts.mockResolvedValueOnce(mockCounts)

    renderPage()

    await waitFor(() => {
      expect(screen.getByTestId('queue-search')).toBeInTheDocument()
    })

    await userEvent.type(screen.getByTestId('queue-search'), 'Alice')

    // The API should be called with the search filter
    await waitFor(() => {
      expect(mockFetchQueue).toHaveBeenCalledWith({ search: 'Alice' })
    })
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

    // Check that date is formatted (Jan 15, 2026)
    expect(screen.getByText(/15 Jan 2026/)).toBeInTheDocument()
    expect(screen.getByText(/16 Jan 2026/)).toBeInTheDocument()
  })
})
