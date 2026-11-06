import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'

import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

interface PlannedFeatureProps {
  icon: LucideIcon
  title: string
  description: string
  capabilities: string[]
  children?: ReactNode
}

/**
 * Explains a feature that is designed but not yet implemented, so placeholder
 * pages stay honest about what currently works.
 */
export function PlannedFeature({
  icon: Icon,
  title,
  description,
  capabilities,
  children,
}: PlannedFeatureProps) {
  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-start gap-4">
            <span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-accent text-accent-foreground">
              <Icon className="size-5" aria-hidden="true" />
            </span>
            <div className="flex min-w-0 flex-1 flex-col gap-1.5">
              <div className="flex flex-wrap items-center gap-2">
                <CardTitle className="text-lg">{title}</CardTitle>
                <Badge variant="outline">Not available yet</Badge>
              </div>
              <CardDescription>{description}</CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <h2 className="mb-3 text-sm font-medium text-foreground">Planned capabilities</h2>
          <ul className="grid gap-2 sm:grid-cols-2">
            {capabilities.map((capability) => (
              <li
                key={capability}
                className="rounded-lg border bg-muted/40 px-3 py-2 text-sm text-muted-foreground"
              >
                {capability}
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>
      {children}
    </div>
  )
}
