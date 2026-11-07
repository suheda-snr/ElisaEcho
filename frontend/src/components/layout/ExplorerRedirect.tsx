import { Navigate, useLocation } from 'react-router'

/** Old routes (/search, /network, /graph) open the matching Knowledge Explorer tab and keep
their query string (?q=, ?group=). */
export function ExplorerRedirect({ tab }: { tab: 'search' | 'all' | 'relationships' }) {
  const { search } = useLocation()
  const params = new URLSearchParams(search)
  if (!params.has('tab')) params.set('tab', tab)
  return <Navigate to={`/knowledge?${params.toString()}`} replace />
}
