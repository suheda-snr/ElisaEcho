import type { ReactNode } from 'react'
import { useLocation } from 'react-router'

import { navItemFor } from '@/lib/navigation'

interface PageHeaderProps {
  /** Defaults to the navigation label and description of the current route. */
  title?: string
  description?: ReactNode
  actions?: ReactNode
  children?: ReactNode
}

/** Page title row: title and one line of context on the left, actions on the right. */
export function PageHeader({ title, description, actions, children }: PageHeaderProps) {
  const item = navItemFor(useLocation().pathname)
  const text = description ?? item?.description
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0">
          <h1 className="text-[22px] leading-tight font-semibold tracking-[-0.01em] text-foreground text-balance">
            {title ?? item?.label}
          </h1>
          {text && <p className="mt-1 max-w-3xl text-sm text-muted-foreground">{text}</p>}
        </div>
        {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
      </div>
      {children}
    </div>
  )
}
