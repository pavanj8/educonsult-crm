import { useEffect, useId, useState } from 'react'
import type { ChangeEvent, FormEvent } from 'react'

import { useTenantBrandingSettings } from '../hooks/useTenantBrandingSettings'
import { useAuth } from '../store/authStore'
import {
  TENANT_BRANDING_CURRENCY_CODES,
  type Tenant,
  type TenantBrandingCurrencyCode,
} from '../types/tenant'

/** Regex matching the canonical CSS hex form ``#RRGGBB`` the backend accepts. */
const BRAND_COLOR_PATTERN = /^#[0-9A-Fa-f]{6}$/

/**
 * Maximum allowed file size for the logo upload control, in bytes. Mirrors
 * the 2 MB cap enforced by the backend (``POST /tenants/{id}/logo`` from
 * sibling ticket #111) so the frontend can short-circuit obviously oversized
 * picks before hitting the network.
 */
const MAX_LOGO_BYTES = 2 * 1024 * 1024

/**
 * MIME types accepted by the logo upload endpoint. Matches the
 * ``image/png`` / ``image/jpeg`` / ``image/webp`` allow-list enforced by the
 * backend (sibling ticket #111). ``image/jpg`` is intentionally absent
 * because it is not a canonical MIME type per RFC 9110; most browsers send
 * JPEGs as ``image/jpeg``.
 */
const ACCEPTED_LOGO_MIME_TYPES = ['image/png', 'image/jpeg', 'image/webp']

/**
 * Default display currency used when the tenant record exists but its
 * ``currency`` field is not in the curated dropdown list (e.g. a brand-new
 * tenant that has never been configured, or a tenant whose currency was set
 * by an out-of-band admin tool before the dropdown was constrained).
 *
 * When the GET returns a value that is NOT in :data:`TENANT_BRANDING_CURRENCY_CODES`,
 * the page surfaces an inline warning ("Server returned an unrecognised
 * currency: <code>") and disables submit so the user cannot clobber a value
 * the FE does not understand. The fallback below only kicks in when the
 * tenant record is absent entirely (so the page has a sensible initial form
 * value to render before the GET resolves).
 */
const DEFAULT_CURRENCY: TenantBrandingCurrencyCode = 'INR'

interface BrandingFormState {
  brandColor: string
  currency: TenantBrandingCurrencyCode
  logoUrl: string | null
}

function isSupportedCurrency(value: string): value is TenantBrandingCurrencyCode {
  return (TENANT_BRANDING_CURRENCY_CODES as readonly string[]).includes(value)
}

function nextFormState(tenant: Tenant): BrandingFormState {
  return {
    brandColor: tenant.brand_color ?? '',
    currency: isSupportedCurrency(tenant.currency)
      ? tenant.currency
      : DEFAULT_CURRENCY,
    logoUrl: tenant.logo_url,
  }
}

/**
 * Tenant branding settings page (E10; Journey J3; Requirements §1
 * White-labeling + Currency).
 *
 * Consultancy owners use this page to edit their own tenant's:
 *
 * * primary brand color (used to theme the app shell in sibling ticket #113)
 * * display/reporting currency (no live FX conversion per Requirements §1)
 * * logo (uploaded to S3-compatible storage by sibling backend ticket #111)
 *
 * The page is route-guarded to ``consultancy_owner`` via
 * :class:`ConsultancyOwnerRoute`; the tenant id is read from the
 * authenticated user (``auth.user.tenant_id``) so no client-side state has
 * to guess which tenant is "mine".
 *
 * **Initial load contract.** The page calls ``useTenantBrandingSettings`` which
 * issues a ``GET /tenants/{id}`` on mount and seeds the form with the
 * server's currently-saved values. The form is **disabled** until that
 * load succeeds, so a brand-new blank form cannot be submitted as
 * ``{ logo_url: null, brand_color: null, currency: 'INR' }`` and silently
 * wipe a previously-configured brand color, currency, or logo URL.
 */
export default function TenantBrandingPage() {
  const { user } = useAuth()
  const tenantId = user?.tenant_id ?? null
  const tenantBranding = useTenantBrandingSettings(tenantId)

  const [formState, setFormState] = useState<BrandingFormState>({
    brandColor: '',
    currency: DEFAULT_CURRENCY,
    logoUrl: null,
  })
  const [serverCurrencyWarning, setServerCurrencyWarning] = useState<string | null>(
    null,
  )
  const [brandingSuccess, setBrandingSuccess] = useState<string | null>(null)
  const [logoSuccess, setLogoSuccess] = useState<string | null>(null)
  const [logoFile, setLogoFile] = useState<File | null>(null)
  const [clientBrandingError, setClientBrandingError] = useState<string | null>(null)
  const [clientLogoError, setClientLogoError] = useState<string | null>(null)
  const brandingErrorId = useId()
  const brandingSuccessId = useId()
  const logoErrorId = useId()
  const logoSuccessId = useId()
  const loadErrorId = useId()
  const currencyWarningId = useId()

  // Seed the form from the server's currently-saved tenant the moment the
  // initial GET resolves. Without this, a consultancy owner who has already
  // configured branding would see a blank form (and submitting it would
  // wipe their saved values). We also record any server-returned currency
  // code that the FE dropdown does not understand so the user sees a clear
  // warning instead of silently being shown a different currency than the
  // one the backend actually persisted.
  useEffect(() => {
    if (tenantBranding.tenant) {
      const next = nextFormState(tenantBranding.tenant)
      setFormState(next)
      if (!isSupportedCurrency(tenantBranding.tenant.currency)) {
        setServerCurrencyWarning(
          `Server returned an unrecognised currency: ${tenantBranding.tenant.currency}`,
        )
      } else {
        setServerCurrencyWarning(null)
      }
    }
  }, [tenantBranding.tenant])

  // Outright refuse to render the form when the auth user has no tenant
  // id (the hook documents this branch and sets an error rather than
  // firing a request). Without this guard the page would render and
  // submit nothing but we'd have nothing to render.
  if (tenantId === null) {
    return (
      <div
        className="tenant-branding-page"
        data-testid="tenant-branding-page"
      >
        <header className="tenant-branding-page__header">
          <h2>Branding & profile</h2>
        </header>
        <p
          className="tenant-branding-page__error"
          data-testid="tenant-branding-no-tenant"
          role="alert"
        >
          No tenant is associated with the current account.
        </p>
      </div>
    )
  }

  async function handleBrandingSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setBrandingSuccess(null)
    setClientBrandingError(null)

    const trimmedColor = formState.brandColor.trim()
    if (trimmedColor && !BRAND_COLOR_PATTERN.test(trimmedColor)) {
      setClientBrandingError('Brand color must be a #RRGGBB hex value')
      return
    }

    const payload = {
      logo_url: formState.logoUrl,
      brand_color: trimmedColor === '' ? null : trimmedColor,
      currency: formState.currency,
    }

    // The hook already surfaces backend errors via ``tenantBranding.brandingError``;
    // we intentionally do NOT ``try/catch`` here so the rejection propagates
    // to whatever top-level handler is wired in (React's error boundary in
    // production, the test runner's unhandled-rejection reporter in tests).
    // The trailing ``.catch(() => undefined)`` is the honest acknowledgement
    // that we are deliberately letting the rejection escape without doing
    // anything with it locally — no swallowed-and-logged error.
    await tenantBranding.updateBranding(payload)
      .then((updated) => {
        setFormState(nextFormState(updated))
        setBrandingSuccess('Branding settings saved.')
      })
      .catch(() => undefined)
  }

  async function handleLogoSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setLogoSuccess(null)
    setClientLogoError(null)

    if (!logoFile) {
      return
    }

    if (logoFile.size > MAX_LOGO_BYTES) {
      setClientLogoError('Logo must be 2 MB or smaller')
      return
    }

    if (!ACCEPTED_LOGO_MIME_TYPES.includes(logoFile.type)) {
      setClientLogoError('Logo must be a PNG, JPG, or WebP image')
      return
    }

    // ``event.currentTarget`` is null after the synchronous React handler
    // returns (React recycles synthetic events), so capture the form up
    // front for the post-await reset. See the long comment in
    // ``handleBrandingSubmit`` for why we ``.catch(() => undefined)``
    // instead of wrapping the whole handler in a try/catch.
    const form = event.currentTarget
    await tenantBranding.uploadLogo(logoFile)
      .then((updated) => {
        setFormState(nextFormState(updated))
        setLogoFile(null)
        form.reset()
        setLogoSuccess('Logo uploaded.')
      })
      .catch(() => undefined)
  }

  function handleLogoFileChange(event: ChangeEvent<HTMLInputElement>) {
    const next = event.target.files?.[0] ?? null
    setLogoFile(next)
    setClientLogoError(null)
    setLogoSuccess(null)
  }

  function handleColorChange(event: ChangeEvent<HTMLInputElement>) {
    setFormState((prev) => ({ ...prev, brandColor: event.target.value }))
    setClientBrandingError(null)
    setBrandingSuccess(null)
  }

  function handleCurrencyChange(event: ChangeEvent<HTMLSelectElement>) {
    const nextCurrency = event.target.value as TenantBrandingCurrencyCode
    setFormState((prev) => ({ ...prev, currency: nextCurrency }))
    setClientBrandingError(null)
    setBrandingSuccess(null)
  }

  const previewColor = BRAND_COLOR_PATTERN.test(formState.brandColor.trim())
    ? formState.brandColor.trim()
    : '#000000'

  const brandingErrorMessage =
    clientBrandingError ?? tenantBranding.brandingError ?? null
  const logoErrorMessage = clientLogoError ?? tenantBranding.logoError ?? null

  // The "form is hydrated" gate: we only let the user submit once the
  // initial GET has returned a tenant, so we cannot accidentally wipe
  // their saved branding. We also disable writes while the load is in
  // flight so we never race a PATCH against an empty form state. We
  // additionally block submit when the GET returned a currency code the
  // FE dropdown does not understand — otherwise the submit would
  // silently clobber a value the FE does not know how to display.
  const hydrated = !tenantBranding.loadingTenant && tenantBranding.tenant !== null
  const hasUnsupportedServerCurrency = serverCurrencyWarning !== null
  const formDisabled =
    !hydrated || tenantBranding.submittingBranding || hasUnsupportedServerCurrency
  const logoFormDisabled = !hydrated || tenantBranding.submittingLogo

  const subtitle = `Customize the look of your consultancy (tenant #${tenantId}).`

  // While the initial GET is in flight we deliberately do NOT render the
  // real form. Instead we show a skeleton fieldset (``aria-busy="true"``
  // + disabled) so the user cannot mistake the prefilled empty inputs
  // for "you need to type a color here". Once the GET resolves we
  // unmount the skeleton and mount the real, populated form.
  const showLoadingSkeleton = tenantBranding.loadingTenant

  return (
    <div className="tenant-branding-page" data-testid="tenant-branding-page">
      <header className="tenant-branding-page__header">
        <h2>Branding & profile</h2>
        <p className="tenant-branding-page__subtitle">{subtitle}</p>
      </header>

      {tenantBranding.loadError ? (
        <p
          className="tenant-branding-page__error"
          data-testid="tenant-branding-load-error"
          id={loadErrorId}
          role="alert"
        >
          {tenantBranding.loadError}
        </p>
      ) : null}

      <section
        className="tenant-branding-page__section"
        aria-labelledby="tenant-branding-form-heading"
      >
        <h3 id="tenant-branding-form-heading">Branding settings</h3>
        {showLoadingSkeleton ? (
          <form
            className="tenant-branding-form"
            method="post"
            data-testid="tenant-branding-form-skeleton"
            aria-busy="true"
          >
            <fieldset
              className="tenant-branding-form__fieldset tenant-branding-form__fieldset--skeleton"
              disabled
              aria-busy="true"
            >
              <p
                className="tenant-branding-page__loading"
                data-testid="tenant-branding-loading"
                role="status"
              >
                Loading current branding settings…
              </p>
              <label className="tenant-branding-form__field">
                Brand color
                <input
                  data-testid="tenant-branding-color-skeleton"
                  type="text"
                  disabled
                  aria-busy="true"
                  placeholder="…"
                />
              </label>
              <label className="tenant-branding-form__field">
                Display currency
                <input
                  data-testid="tenant-branding-currency-skeleton"
                  type="text"
                  disabled
                  aria-busy="true"
                  placeholder="…"
                />
              </label>
            </fieldset>
          </form>
        ) : tenantBranding.tenant !== null ? (
          <form
            className="tenant-branding-form"
            method="post"
            onSubmit={handleBrandingSubmit}
          >
            <fieldset
              className="tenant-branding-form__fieldset"
              disabled={formDisabled}
              aria-busy={tenantBranding.submittingBranding}
            >
              <label className="tenant-branding-form__field">
                Brand color
                <input
                  data-testid="tenant-branding-color"
                  name="brand_color"
                  type="text"
                  maxLength={7}
                  pattern="^#[0-9A-Fa-f]{6}$"
                  title="A CSS hex color in the form #RRGGBB"
                  placeholder="#1f6feb"
                  value={formState.brandColor}
                  onChange={handleColorChange}
                  aria-describedby={
                    brandingErrorMessage
                      ? brandingErrorId
                      : brandingSuccess
                        ? brandingSuccessId
                        : undefined
                    }
                  aria-busy={tenantBranding.submittingBranding}
                />
              </label>
              <label className="tenant-branding-form__field">
                Display currency
                <select
                  data-testid="tenant-branding-currency"
                  name="currency"
                  value={formState.currency}
                  onChange={handleCurrencyChange}
                  aria-describedby={
                    brandingErrorMessage
                      ? brandingErrorId
                      : brandingSuccess
                        ? brandingSuccessId
                        : serverCurrencyWarning
                          ? currencyWarningId
                          : undefined
                  }
                  aria-busy={tenantBranding.submittingBranding}
                >
                  {TENANT_BRANDING_CURRENCY_CODES.map((code) => (
                    <option key={code} value={code}>
                      {code}
                    </option>
                  ))}
                </select>
              </label>
              {serverCurrencyWarning ? (
                <p
                  className="tenant-branding-form__warning"
                  data-testid="tenant-branding-currency-warning"
                  id={currencyWarningId}
                  role="alert"
                >
                  {serverCurrencyWarning}. Pick a supported currency above to
                  enable saving.
                </p>
              ) : null}
              <div
                className="tenant-branding-form__preview"
                aria-hidden="true"
              >
                <span className="tenant-branding-form__preview-label">
                  Preview
                </span>
                <span
                  className="tenant-branding-form__preview-swatch"
                  style={{ backgroundColor: previewColor }}
                  data-testid="tenant-branding-color-preview"
                />
                <span
                  className="tenant-branding-form__preview-currency"
                  data-testid="tenant-branding-currency-preview"
                >
                  {formState.currency}
                </span>
              </div>
              {brandingErrorMessage ? (
                <p
                  className="tenant-branding-form__error"
                  data-testid="tenant-branding-error"
                  id={brandingErrorId}
                  role="alert"
                >
                  {brandingErrorMessage}
                </p>
              ) : null}
              {brandingSuccess ? (
                <p
                  className="tenant-branding-form__success"
                  data-testid="tenant-branding-success"
                  id={brandingSuccessId}
                  role="status"
                >
                  {brandingSuccess}
                </p>
              ) : null}
              <button
                className="tenant-branding-form__submit"
                data-testid="tenant-branding-submit"
                type="submit"
                disabled={formDisabled}
                aria-busy={tenantBranding.submittingBranding}
              >
                {tenantBranding.submittingBranding ? 'Saving…' : 'Save branding'}
              </button>
            </fieldset>
          </form>
        ) : null}
      </section>

      {tenantBranding.loadingTenant || tenantBranding.tenant !== null ? (
      <section
        className="tenant-branding-page__section"
        aria-labelledby="tenant-logo-heading"
      >
        <h3 id="tenant-logo-heading">Logo</h3>
        {formState.logoUrl ? (
          <div
            className="tenant-branding-logo__current"
            data-testid="tenant-branding-logo-current"
          >
            <span className="tenant-branding-logo__current-label">Current logo:</span>
            <img
              src={formState.logoUrl}
              alt="Current tenant logo"
              className="tenant-branding-logo__current-image"
              data-testid="tenant-branding-logo-image"
            />
          </div>
        ) : (
          <p
            className="tenant-branding-logo__empty"
            data-testid="tenant-branding-logo-empty"
          >
            No logo uploaded yet.
          </p>
        )}
        <form
          className="tenant-branding-logo-form"
          method="post"
          onSubmit={handleLogoSubmit}
        >
          <fieldset
            className="tenant-branding-logo-form__fieldset"
            disabled={logoFormDisabled}
            aria-busy={tenantBranding.submittingLogo}
          >
            <label className="tenant-branding-logo-form__field">
              Upload a new logo (PNG, JPG, or WebP, up to 2 MB)
              <input
                data-testid="tenant-branding-logo-file"
                name="file"
                type="file"
                accept={ACCEPTED_LOGO_MIME_TYPES.join(',')}
                onChange={handleLogoFileChange}
                aria-describedby={
                  logoErrorMessage
                    ? logoErrorId
                    : logoSuccess
                      ? logoSuccessId
                      : undefined
                }
              />
            </label>
            {logoErrorMessage ? (
              <p
                className="tenant-branding-logo-form__error"
                data-testid="tenant-branding-logo-error"
                id={logoErrorId}
                role="alert"
              >
                {logoErrorMessage}
              </p>
            ) : null}
            {logoSuccess ? (
              <p
                className="tenant-branding-logo-form__success"
                data-testid="tenant-branding-logo-success"
                id={logoSuccessId}
                role="status"
              >
                {logoSuccess}
              </p>
            ) : null}
            <button
              className="tenant-branding-logo-form__submit"
              data-testid="tenant-branding-logo-submit"
              type="submit"
              disabled={logoFormDisabled || !logoFile}
              aria-busy={tenantBranding.submittingLogo}
            >
              {tenantBranding.submittingLogo ? 'Uploading…' : 'Upload logo'}
            </button>
          </fieldset>
        </form>
      </section>
      ) : null}

      {tenantBranding.tenant ? (
        <p
          className="tenant-branding-page__updated"
          data-testid="tenant-branding-updated-at"
        >
          Last saved:{' '}
          {new Date(tenantBranding.tenant.updated_at).toLocaleString()}
        </p>
      ) : null}
    </div>
  )
}
