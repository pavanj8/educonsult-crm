/**
 * Seeded demo accounts for one-click sign-in on the login page.
 *
 * Mirrors `backend/app/seed/catalog.py` — one account per role from the Apex
 * demo tenant, plus the platform super admin. These only work against a
 * database that has had the demo seed applied (`python -m app.seed`); on any
 * other database the sign-in simply fails as a normal bad-credentials error.
 *
 * SECURITY: this ships real, working credentials into the bundle, so it is
 * gated off by default and must never be enabled on an internet-facing
 * deployment holding real data. See `demoLoginsEnabled()`.
 */

/** Matches DEMO_PASSWORD in backend/app/seed/catalog.py. */
export const DEMO_PASSWORD = 'demo-password'

export interface DemoAccount {
  /** Seeded login email. */
  email: string
  /** Human name from the seed, so the picker reads like a person not a fixture. */
  name: string
  /** Role label shown on the button. */
  role: string
  /** Short note on what this role can actually reach, to make the list useful. */
  hint: string
}

export const DEMO_ACCOUNTS: readonly DemoAccount[] = [
  {
    email: 'super_admin@demo.test',
    name: 'Priya Sharma',
    role: 'Super Admin',
    hint: 'Tenants, platform analytics, billing',
  },
  {
    email: 'owner@apex.demo.test',
    name: 'Rajesh Mehta',
    role: 'Consultancy Owner',
    hint: 'Cross-branch dashboard, staff, branding',
  },
  {
    email: 'manager.mumbai@apex.demo.test',
    name: 'Anita Desai',
    role: 'Branch Manager',
    hint: 'Branch analytics for Mumbai HQ',
  },
  {
    email: 'counselor@demo.test',
    name: 'Vikram Patel',
    role: 'Counselor',
    hint: 'Assigned applications and student pipeline',
  },
  {
    email: 'verifier@apex.demo.test',
    name: 'Sneha Iyer',
    role: 'Document Verifier',
    hint: 'Document verification queue',
  },
  {
    email: 'visa@apex.demo.test',
    name: 'Arjun Singh',
    role: 'Visa Processor',
    hint: 'Visa tracking and outcomes',
  },
  {
    email: 'reception@apex.demo.test',
    name: 'Meera Nair',
    role: 'Receptionist',
    hint: 'Walk-in intake',
  },
  {
    email: 'student@apex.demo.test',
    name: 'Rahul Kumar',
    role: 'Student',
    hint: 'Own application status and documents',
  },
]

/**
 * Whether to offer one-click demo sign-in: off unless this is a dev server, or
 * someone deliberately set `VITE_ENABLE_DEMO_LOGINS=true` for a throwaway demo
 * deployment.
 *
 * This is the RUNTIME guard, and on its own it only stops the picker
 * rendering — the credentials below would still be in the production bundle
 * for anyone who opened the JS. What actually keeps them out is the matching
 * literal condition at the render site in LoginPage.tsx: written inline, Vite
 * substitutes `import.meta.env.DEV` with `false` and Rollup drops this whole
 * module. Verified by grepping dist/ after a production build.
 *
 * So: do not "simplify" LoginPage to call this function instead. Both layers
 * are load-bearing, and only the inline one strips the secrets.
 */
export function demoLoginsEnabled(): boolean {
  return import.meta.env.DEV || import.meta.env.VITE_ENABLE_DEMO_LOGINS === 'true'
}
