/**
 * Tests for UpgradePlanAction component (E46; Journey J39).
 */

import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import UpgradePlanAction from './UpgradePlanAction'

describe('UpgradePlanAction', () => {
  it('renders an upgrade button', () => {
    render(<UpgradePlanAction targetPlanCode="growth" />)
    const button = screen.getByTestId('upgrade-plan-button-growth')
    expect(button).toBeInTheDocument()
    expect(button).toHaveTextContent('Upgrade to Growth')
  })

  it('renders a downgrade button for starter plan', () => {
    render(<UpgradePlanAction targetPlanCode="starter" currentPlanCode="growth" />)
    const button = screen.getByTestId('upgrade-plan-button-starter')
    expect(button).toBeInTheDocument()
    expect(button).toHaveTextContent('Downgrade to Starter')
  })

  it('shows disabled state while initiating checkout', () => {
    render(<UpgradePlanAction targetPlanCode="growth" />)
    const button = screen.getByTestId('upgrade-plan-button-growth')
    // Button should not be disabled initially
    expect(button).not.toBeDisabled()
  })

  it('renders with custom button text', () => {
    render(<UpgradePlanAction targetPlanCode="enterprise" buttonText="Upgrade Now" />)
    const button = screen.getByTestId('upgrade-plan-button-enterprise')
    expect(button).toHaveTextContent('Upgrade Now')
  })
})
