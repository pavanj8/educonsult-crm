import { useState } from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import StudyPreferencesFieldset from './StudyPreferencesFieldset'

const mockCountries = [{ id: 1, tenant_id: 10, name: 'Canada', code: 'CA' }]
const mockUniversities = [{ id: 10, tenant_id: 10, country_id: 1, name: 'University of Toronto' }]
const mockPrograms = [{ id: 100, tenant_id: 10, university_id: 10, name: 'Computer Science MSc' }]

function mockMasterDataFetch() {
  return vi.fn((url: string) => {
    if (url.endsWith('/tenants/apex/countries')) {
      return Promise.resolve({
        ok: true,
        status: 200,
        json: async () => mockCountries,
      })
    }
    if (url.endsWith('/tenants/apex/universities?country_id=1')) {
      return Promise.resolve({
        ok: true,
        status: 200,
        json: async () => mockUniversities,
      })
    }
    if (url.endsWith('/tenants/apex/programs?university_id=10')) {
      return Promise.resolve({
        ok: true,
        status: 200,
        json: async () => mockPrograms,
      })
    }
    return Promise.resolve({
      ok: false,
      status: 404,
      json: async () => ({ detail: 'Not found' }),
    })
  })
}

function ControlledFieldset({ tenantSlug = 'apex' }: { tenantSlug?: string }) {
  const [countryId, setCountryId] = useState<number | ''>('')
  const [universityId, setUniversityId] = useState<number | ''>('')
  const [programId, setProgramId] = useState<number | ''>('')

  return (
    <StudyPreferencesFieldset
      tenantSlug={tenantSlug}
      countryId={countryId}
      universityId={universityId}
      programId={programId}
      onCountryChange={(value) => {
        setCountryId(value)
        setUniversityId('')
        setProgramId('')
      }}
      onUniversityChange={(value) => {
        setUniversityId(value)
        setProgramId('')
      }}
      onProgramChange={setProgramId}
    />
  )
}

describe('StudyPreferencesFieldset', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('renders cascading country, university, and program dropdowns', async () => {
    vi.stubGlobal('fetch', mockMasterDataFetch())

    render(<ControlledFieldset />)

    expect(screen.getByRole('group', { name: 'Study preferences' })).toBeInTheDocument()
    expect(screen.getByTestId('register-target-country')).toBeInTheDocument()
    expect(screen.getByTestId('register-target-university')).toBeInTheDocument()
    expect(screen.getByTestId('register-target-program')).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByRole('option', { name: 'Canada' })).toBeInTheDocument()
    })
  })

  it('loads universities after a country is selected', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('fetch', mockMasterDataFetch())

    render(<ControlledFieldset />)

    await waitFor(() => {
      expect(screen.getByRole('option', { name: 'Canada' })).toBeInTheDocument()
    })

    await user.selectOptions(screen.getByTestId('register-target-country'), '1')

    await waitFor(() => {
      expect(screen.getByRole('option', { name: 'University of Toronto' })).toBeInTheDocument()
    })
  })

  it('disables university and program selects until upstream values are chosen', async () => {
    vi.stubGlobal('fetch', mockMasterDataFetch())
    render(<ControlledFieldset />)

    await waitFor(() => {
      expect(screen.getByRole('option', { name: 'Canada' })).toBeInTheDocument()
    })

    expect(screen.getByTestId('register-target-university')).toBeDisabled()
    expect(screen.getByTestId('register-target-program')).toBeDisabled()
    expect(screen.getByText('Select a country first')).toBeInTheDocument()
  })

  it('shows an error alert when country loading fails', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        json: async () => ({ detail: 'Tenant not found' }),
      }),
    )

    render(<ControlledFieldset tenantSlug="missing" />)

    await waitFor(() => {
      expect(screen.getByTestId('register-countries-error')).toHaveTextContent(
        'Consultancy not found',
      )
    })
  })
})
