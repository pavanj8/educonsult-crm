import { BrowserRouter, Route, Routes } from 'react-router-dom'

import AppLayout from '../layouts/AppLayout'
import HomePage from '../pages/HomePage'
import NotFoundPage from '../pages/NotFoundPage'

export function AppRouter() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppLayout />}>
          <Route index element={<HomePage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
