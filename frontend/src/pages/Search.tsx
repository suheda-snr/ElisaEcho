import { Search as SearchIcon } from 'lucide-react'

import { PlannedFeature } from '@/components/PlannedFeature'
import { Card, CardContent } from '@/components/ui/card'

export default function Search() {
  return (
    <PlannedFeature
      icon={SearchIcon}
      title="Search Knowledge"
      description="Find relevant incidents, procedures and expert insights by meaning, not just matching words."
      capabilities={[
        'Semantic vector search over captured knowledge',
        'Keyword search for exact identifiers and error codes',
        'Context from related equipment, incidents and experts',
        'Evidence and source references for every result',
      ]}
    >
      <Card>
        <CardContent>
          <label
            htmlFor="knowledge-search"
            className="mb-2 block text-sm font-medium text-foreground"
          >
            Search query
          </label>
          <div className="relative">
            <SearchIcon
              className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
              aria-hidden="true"
            />
            <input
              id="knowledge-search"
              type="search"
              disabled
              placeholder="Search is not available yet"
              className="h-10 w-full cursor-not-allowed rounded-lg border bg-muted/40 pr-3 pl-9 text-sm text-muted-foreground placeholder:text-muted-foreground"
            />
          </div>
        </CardContent>
      </Card>
    </PlannedFeature>
  )
}
