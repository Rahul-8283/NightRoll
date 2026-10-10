import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { RouterProvider } from 'react-router'
import { MissingConfig } from './components/MissingConfig'
import { missingConfig } from './config'
import { router } from './routes'
import './index.css'

const queryClient = new QueryClient()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      {missingConfig.length > 0 ? <MissingConfig /> : <RouterProvider router={router} />}
    </QueryClientProvider>
  </StrictMode>,
)
