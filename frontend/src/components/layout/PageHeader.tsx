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

/** Consistent page title row: title + one-line explanation on the left, actions on the right. */
export function PageHeader({ title, description, actions, children }: PageHeaderProps) {
  const item = navItemFor(useLocation().pathname)
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight text-foreground">
            {item?.step && (
              <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-primary text-sm font-semibold text-primary-foreground">
                {item.step}
              </span>
            )}
            {title ?? item?.label}
          </h1>
          <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
            {description ?? item?.description}
          </p>
        </div>
        {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
      </div>
      {children}
    </div>
  )
}
