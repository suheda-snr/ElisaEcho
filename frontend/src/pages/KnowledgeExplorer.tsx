import { BookOpenText, Network, Search as SearchIcon } from 'lucide-react'
import { lazy, Suspense } from 'react'
import { useSearchParams } from 'react-router'

import { PageHeader } from '@/components/layout/PageHeader'
import { cn } from '@/lib/utils'

const SearchTab = lazy(() => import('@/pages/Search'))
const AllKnowledgeTab = lazy(() => import('@/pages/KnowledgeBase'))
const RelationshipsTab = lazy(() => import('@/pages/KnowledgeNetwork'))

export type Tab = 'search' | 'all' | 'relationships'

const TABS: { value: Tab; label: string; icon: typeof SearchIcon }[] = [
  { value: 'search', label: 'Search', icon: SearchIcon },
  { value: 'all', label: 'All knowledge', icon: BookOpenText },
  { value: 'relationships', label: 'Relationships', icon: Network },
]

/** The tab follows the URL, so links like ?item=, ?group= and ?q= open the right view. */
function tabFrom(params: URLSearchParams): Tab {
  const explicit = params.get('tab')
  if (explicit === 'search' || explicit === 'all' || explicit === 'relationships') return explicit
  if (params.has('group')) return 'relationships'
  if (params.has('item')) return 'all'
  return 'search'
}

export default function KnowledgeExplorer() {
  const [params, setParams] = useSearchParams()
  const tab = tabFrom(params)

  return (
    <div className="flex flex-col gap-5">
      <PageHeader>
        <div role="tablist" aria-label="Knowledge Explorer views" className="flex gap-1 border-b">
          {TABS.map(({ value, label, icon: Icon }) => (
            <button
              key={value}
              type="button"
              role="tab"
              aria-selected={tab === value}
              onClick={() => setParams({ tab: value })}
              className={cn(
                '-mb-px inline-flex items-center gap-2 border-b-2 px-3 py-2.5 text-sm font-medium transition-colors',
                'focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none',
                tab === value
                  ? 'border-primary text-foreground'
                  : 'border-transparent text-muted-foreground hover:text-foreground',
              )}
            >
              <Icon className="size-4" aria-hidden="true" />
              {label}
            </button>
          ))}
        </div>
      </PageHeader>
      <Suspense fallback={<p className="text-sm text-muted-foreground">Loading…</p>}>
        {tab === 'search' && <SearchTab />}
        {tab === 'all' && <AllKnowledgeTab />}
        {tab === 'relationships' && <RelationshipsTab />}
      </Suspense>
    </div>
  )
}
