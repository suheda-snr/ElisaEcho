import type { ComponentType } from 'react'
import { createBrowserRouter, Navigate, RouterProvider } from 'react-router'

import { AppLayout } from '@/components/layout/AppLayout'
import { ExplorerRedirect } from '@/components/layout/ExplorerRedirect'

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
      { path: 'knowledge', lazy: page(() => import('@/pages/KnowledgeExplorer')) },
      { path: 'integrations', lazy: page(() => import('@/pages/Integrations')) },
      // Old route of the page before it became Live Discovery.
      { path: 'capture', element: <Navigate to="/discovery" replace /> },
      // Search, Knowledge Base and Knowledge Network are tabs of the Knowledge Explorer now.
      { path: 'search', element: <ExplorerRedirect tab="search" /> },
      { path: 'troubleshoot', lazy: page(() => import('@/pages/Troubleshoot')) },
      { path: 'network', element: <ExplorerRedirect tab="relationships" /> },
      { path: 'graph', element: <ExplorerRedirect tab="relationships" /> },
      { path: '*', lazy: page(() => import('@/pages/NotFound')) },
    ],
  },
])

export default function App() {
  return <RouterProvider router={router} />
}
