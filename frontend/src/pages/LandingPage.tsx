import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { REGISTER_PATH } from '../routes/paths'
import { LOGIN_PATH } from '../routes/ProtectedRoute'
import styles from './LandingPage.module.css'

/**
 * Marketing landing page for EduConsult CRM.
 * Public page with hero, features, and CTA sections (E53; Requirements §10).
 */
export default function LandingPage() {
  const { t } = useTranslation()

  return (
    <div className={styles['landing-page']}>
      {/* Hero Section */}
      <section className={styles.hero} aria-labelledby="hero-heading">
        <div className={styles['hero-content']}>
          <h1 id="hero-heading" className={styles['hero-title']}>
            {t('landing.hero.title', 'Streamline Your Education Consultancy')}
          </h1>
          <p className={styles['hero-subtitle']}>
            {t(
              'landing.hero.subtitle',
              'Manage students, track applications, and grow your consultancy with powerful tools built for education consultants.'
            )}
          </p>
          <div className={styles['hero-ctas']}>
            <Link to={REGISTER_PATH} className={`${styles.btn} ${styles['btn-primary']} ${styles['btn-large']}`}>
              {t('landing.hero.cta.start', 'Start Free Trial')}
            </Link>
            <Link to={LOGIN_PATH} className={`${styles.btn} ${styles['btn-secondary']} ${styles['btn-large']}`}>
              {t('landing.hero.cta.login', 'Log In')}
            </Link>
          </div>
        </div>
        <div className={styles['hero-visual']} aria-hidden="true">
          <div className={styles['dashboard-preview']} />
        </div>
      </section>

      {/* Features Section */}
      <section className={styles.features} aria-labelledby="features-heading">
        <div className={styles.container}>
          <h2 id="features-heading" className={styles['section-title']}>
            {t('landing.features.title', 'Everything You Need to Succeed')}
          </h2>
          <p className={styles['section-subtitle']}>
            {t(
              'landing.features.subtitle',
              'Comprehensive tools designed specifically for education consultancies'
            )}
          </p>

          <div className={styles['features-grid']}>
            {/* Feature 1: Student Management */}
            <article className={styles['feature-card']}>
              <div className={styles['feature-icon']} aria-hidden="true">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="48"
                  height="48"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
                  <circle cx="9" cy="7" r="4" />
                  <path d="M22 21v-2a4 4 0 0 0-3-3.87" />
                  <path d="M16 3.13a4 4 0 0 1 0 7.75" />
                </svg>
              </div>
              <h3 className={styles['feature-title']}>
                {t('landing.features.studentManagement.title', 'Student Management')}
              </h3>
              <p className={styles['feature-description']}>
                {t(
                  'landing.features.studentManagement.description',
                  'Track every student from registration to enrollment with comprehensive profiles and application history.'
                )}
              </p>
            </article>

            {/* Feature 2: Application Pipeline */}
            <article className={styles['feature-card']}>
              <div className={styles['feature-icon']} aria-hidden="true">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="48"
                  height="48"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
                </svg>
              </div>
              <h3 className={styles['feature-title']}>
                {t('landing.features.pipeline.title', 'Application Pipeline')}
              </h3>
              <p className={styles['feature-description']}>
                {t(
                  'landing.features.pipeline.description',
                  'Visual pipeline tracking through counseling, documents, visa processing, and enrollment.'
                )}
              </p>
            </article>

            {/* Feature 3: Document Management */}
            <article className={styles['feature-card']}>
              <div className={styles['feature-icon']} aria-hidden="true">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="48"
                  height="48"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <polyline points="14 2 14 8 20 8" />
                  <line x1="16" x2="8" y1="13" y2="13" />
                  <line x1="16" x2="8" y1="17" y2="17" />
                  <line x1="10" x2="8" y1="9" y2="9" />
                </svg>
              </div>
              <h3 className={styles['feature-title']}>
                {t('landing.features.documents.title', 'Document Management')}
              </h3>
              <p className={styles['feature-description']}>
                {t(
                  'landing.features.documents.description',
                  'Secure document upload, verification, and tracking with customizable checklists per program.'
                )}
              </p>
            </article>

            {/* Feature 4: Team Collaboration */}
            <article className={styles['feature-card']}>
              <div className={styles['feature-icon']} aria-hidden="true">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="48"
                  height="48"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                  <circle cx="9" cy="7" r="4" />
                  <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
                  <path d="M16 3.13a4 4 0 0 1 0 7.75" />
                </svg>
              </div>
              <h3 className={styles['feature-title']}>
                {t('landing.features.collaboration.title', 'Team Collaboration')}
              </h3>
              <p className={styles['feature-description']}>
                {t(
                  'landing.features.collaboration.description',
                  'Role-based access for counselors, verifiers, and branch managers with synchronized workflows.'
                )}
              </p>
            </article>

            {/* Feature 5: Analytics & Reporting */}
            <article className={styles['feature-card']}>
              <div className={styles['feature-icon']} aria-hidden="true">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="48"
                  height="48"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <line x1="18" x2="18" y1="20" y2="10" />
                  <line x1="12" x2="12" y1="20" y2="4" />
                  <line x1="6" x2="6" y1="20" y2="14" />
                </svg>
              </div>
              <h3 className={styles['feature-title']}>
                {t('landing.features.analytics.title', 'Analytics & Reporting')}
              </h3>
              <p className={styles['feature-description']}>
                {t(
                  'landing.features.analytics.description',
                  'Track conversion funnels, counselor performance, and branch metrics with detailed dashboards.'
                )}
              </p>
            </article>

            {/* Feature 6: Multi-Branch Support */}
            <article className={styles['feature-card']}>
              <div className={styles['feature-icon']} aria-hidden="true">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="48"
                  height="48"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <rect x="3" y="3" width="7" height="7" />
                  <rect x="14" y="3" width="7" height="7" />
                  <rect x="14" y="14" width="7" height="7" />
                  <rect x="3" y="14" width="7" height="7" />
                </svg>
              </div>
              <h3 className={styles['feature-title']}>
                {t('landing.features.branches.title', 'Multi-Branch Support')}
              </h3>
              <p className={styles['feature-description']}>
                {t(
                  'landing.features.branches.description',
                  'Manage multiple branches seamlessly with centralized oversight and local autonomy.'
                )}
              </p>
            </article>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className={styles['cta-section']} aria-labelledby="cta-heading">
        <div className={styles.container}>
          <h2 id="cta-heading" className={styles['cta-title']}>
            {t('landing.cta.title', 'Ready to Transform Your Consultancy?')}
          </h2>
          <p className={styles['cta-subtitle']}>
            {t(
              'landing.cta.subtitle',
              'Join education consultancies that trust EduConsult CRM to manage their student pipelines.'
            )}
          </p>
          <div className={styles['cta-actions']}>
            <Link to={REGISTER_PATH} className={`${styles.btn} ${styles['btn-primary']} ${styles['btn-large']}`}>
              {t('landing.cta.primary', 'Get Started Free')}
            </Link>
            <Link to={LOGIN_PATH} className={`${styles.btn} ${styles['btn-outline']} ${styles['btn-large']}`}>
              {t('landing.cta.secondary', 'Request Demo')}
            </Link>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className={styles['landing-footer']}>
        <div className={styles.container}>
          <p className={styles['footer-text']}>
            {t('landing.footer.rights', '© 2024 EduConsult CRM. All rights reserved.')}
          </p>
        </div>
      </footer>
    </div>
  )
}
