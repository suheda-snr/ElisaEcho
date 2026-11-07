import { ChevronRight } from 'lucide-react'
import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

/** Collapsible section (native <details>, keyboard accessible). */
export function Disclosure({
  title,
  count,
  defaultOpen = false,
  children,
  className,
}: {
  title: ReactNode
  count?: number
  defaultOpen?: boolean
  children: ReactNode
  className?: string
}) {
  return (
    <details className={cn('group rounded-md border bg-card', className)} open={defaultOpen}>
      <summary className="flex cursor-pointer list-none items-center gap-2 px-3 py-2.5 text-sm font-medium text-foreground transition-colors duration-150 select-none hover:bg-muted/60 [&::-webkit-details-marker]:hidden">
        <ChevronRight
          className="size-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-90"
          aria-hidden="true"
        />
        <span className="min-w-0 flex-1">{title}</span>
        {count !== undefined && (
          <span className="rounded-full bg-muted px-2 text-xs text-muted-foreground tabular-nums">
            {count}
          </span>
        )}
      </summary>
      <div className="border-t px-3 py-3">{children}</div>
    </details>
  )
}
