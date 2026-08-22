import { AppRouter } from './routes'
import { AuthProvider } from './store/authStore'
import { BrandingProvider } from './store/brandingStore'

export default function App() {
  return (
    <AuthProvider>
      <BrandingProvider>
        <AppRouter />
      </BrandingProvider>
    </AuthProvider>
  )
}
