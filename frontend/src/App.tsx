import type { ComponentType } from 'react'
import { createBrowserRouter, Navigate, RouterProvider } from 'react-router'

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
      { path: 'discovery', lazy: page(() => import('@/pages/LiveDiscovery')) },
      { path: 'knowledge', lazy: page(() => import('@/pages/KnowledgeBase')) },
      { path: 'integrations', lazy: page(() => import('@/pages/Integrations')) },
      // Old route of the page before it became Live Discovery.
      { path: 'capture', element: <Navigate to="/discovery" replace /> },
      { path: 'search', lazy: page(() => import('@/pages/Search')) },
      { path: 'troubleshoot', lazy: page(() => import('@/pages/Troubleshoot')) },
      { path: 'network', lazy: page(() => import('@/pages/KnowledgeNetwork')) },
      // The placeholder Knowledge Graph page became the Knowledge Network.
      { path: 'graph', element: <Navigate to="/network" replace /> },
      { path: '*', lazy: page(() => import('@/pages/NotFound')) },
    ],
  },
])

export default function App() {
  return <RouterProvider router={router} />
}
