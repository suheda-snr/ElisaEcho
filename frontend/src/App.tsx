import type { ComponentType } from 'react'
import { createBrowserRouter, RouterProvider } from 'react-router'

import { AppLayout } from '@/components/layout/AppLayout'

// Each page is code-split so heavy libraries (React Flow, Recharts) only load
// on the routes that use them.
const page = (load: () => Promise<{ default: ComponentType }>) => async () => ({
  Component: (await load()).default,
})

const router = createBrowserRouter([
  {
    path: '/',
    Component: AppLayout,
    children: [
      { index: true, lazy: page(() => import('@/pages/Dashboard')) },
      { path: 'capture', lazy: page(() => import('@/pages/Capture')) },
      { path: 'search', lazy: page(() => import('@/pages/Search')) },
      { path: 'troubleshoot', lazy: page(() => import('@/pages/Troubleshoot')) },
      { path: 'graph', lazy: page(() => import('@/pages/KnowledgeGraph')) },
      { path: '*', lazy: page(() => import('@/pages/NotFound')) },
    ],
  },
])

export default function App() {
  return <RouterProvider router={router} />
}
