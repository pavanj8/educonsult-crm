/**
 * Upgrade/Downgrade Plan action component for Consultancy Owners (E46; Journey J39).
 *
 * This component renders a button that initiates the Razorpay checkout
 * flow for plan upgrades and downgrades. It uses the usePlanUpgrade hook
 * to create an order and open the Razorpay checkout modal.
 */

import { useState } from 'react'

import { usePlanUpgrade } from '../../hooks/usePlanUpgrade'

interface UpgradePlanActionProps {
  /** The target plan tier code to upgrade/downgrade to. */
  targetPlanCode: 'starter' | 'growth' | 'enterprise'
  /** The current plan tier code (optional, used to determine button text). */
  currentPlanCode?: 'starter' | 'growth' | 'enterprise'
  /** Called after successful payment completion. */
  onSuccess?: () => void
  /** Called when the user cancels the checkout flow. */
  onCancel?: () => void
  /** Custom button text (optional, defaults to "Upgrade to {Plan Name}"). */
  buttonText?: string
}

/**
 * Map plan codes to display names for button text.
 */
const PLAN_NAMES: Record<string, string> = {
  starter: 'Starter',
  growth: 'Growth',
  enterprise: 'Enterprise',
}

/**
 * Component that renders a plan upgrade/downgrade button.
 *
 * When clicked, the button:
 * 1. Creates a Razorpay order via the backend API.
 * 2. Opens the Razorpay checkout modal.
 * 3. Invokes onSuccess when payment succeeds.
 * 4. Invokes onCancel when the user closes the modal.
 *
 * The button shows a loading state while the checkout is being initiated
 * and displays any errors that occur during the process.
 */
export default function UpgradePlanAction({
  targetPlanCode,
  currentPlanCode,
  onSuccess,
  onCancel,
  buttonText,
}: UpgradePlanActionProps) {
  const { loading, error, initiateCheckout } = usePlanUpgrade()
  const [checkoutInitiated, setCheckoutInitiated] = useState(false)

  const handleClick = () => {
    setCheckoutInitiated(true)
    void initiateCheckout(
      targetPlanCode,
      () => {
        setCheckoutInitiated(false)
        onSuccess?.()
      },
      () => {
        setCheckoutInitiated(false)
        onCancel?.()
      }
    )
  }

  // Determine if this is an upgrade or downgrade based on plan hierarchy
  const planHierarchy = ['starter', 'growth', 'enterprise']
  const currentIndex = currentPlanCode ? planHierarchy.indexOf(currentPlanCode) : -1
  const targetIndex = planHierarchy.indexOf(targetPlanCode)
  const isDowngrade = currentPlanCode && targetIndex < currentIndex

  // Default button text
  const defaultButtonText = isDowngrade
    ? `Downgrade to ${PLAN_NAMES[targetPlanCode]}`
    : `Upgrade to ${PLAN_NAMES[targetPlanCode]}`

  return (
    <div className="upgrade-plan-action">
      <button
        type="button"
        onClick={handleClick}
        disabled={loading}
        data-testid={`upgrade-plan-button-${targetPlanCode}`}
        aria-label={defaultButtonText}
      >
        {loading ? 'Opening checkout…' : buttonText || defaultButtonText}
      </button>
      {error && (
        <p role="alert" className="upgrade-plan-action__error" data-testid="upgrade-plan-error">
          {error}
        </p>
      )}
      {checkoutInitiated && !loading && !error && (
        <p className="upgrade-plan-action__info" data-testid="upgrade-plan-info">
          Checkout opened in a new window. Complete the payment to finish the upgrade.
        </p>
      )}
    </div>
  )
}
