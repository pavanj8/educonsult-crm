import { AppRouter } from './routes'
import { AuthProvider } from './store/authStore'
import { BrandingProvider } from './store/brandingStore'
import { I18nProvider } from './store/i18nStore'

export default function App() {
  return (
    <I18nProvider>
      <AuthProvider>
        <BrandingProvider>
          <AppRouter />
        </BrandingProvider>
      </AuthProvider>
    </I18nProvider>
  )
}
