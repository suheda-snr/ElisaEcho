import type { ComponentPropsWithoutRef, ElementType, ReactNode } from 'react'

import { cn } from '@/lib/utils'

/** A single white surface. Prefer one Panel with dividers over several nested cards. */
export function Panel({
  children,
  className,
  as: Tag = 'section',
  ...rest
}: {
  children: ReactNode
  className?: string
  as?: 'section' | 'div' | 'aside'
} & ComponentPropsWithoutRef<ElementType>) {
  return (
    <Tag className={cn('rounded-lg border bg-card text-card-foreground', className)} {...rest}>
      {children}
    </Tag>
  )
}

export function PanelHeader({
  title,
  meta,
  actions,
  className,
}: {
  title: ReactNode
  meta?: ReactNode
  actions?: ReactNode
  className?: string
}) {
  return (
    <header className={cn('flex min-h-12 items-center gap-3 border-b px-4 py-2.5', className)}>
      <h2 className="min-w-0 truncate text-sm font-semibold text-foreground">{title}</h2>
      {meta && <span className="shrink-0 text-xs text-muted-foreground tabular-nums">{meta}</span>}
      {actions && <div className="ml-auto flex shrink-0 items-center gap-2">{actions}</div>}
    </header>
  )
}
