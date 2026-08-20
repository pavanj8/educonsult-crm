import { AppRouter } from './routes'
import { AuthProvider } from './store/authStore'

export default function App() {
  return (
    <AuthProvider>
      <AppRouter />
    </AuthProvider>
  )
}
