import { Sparkles } from 'lucide-react'
import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

/**
 * The signature treatment for AI-discovered knowledge: a blue-tinted block that is used
 * the same way everywhere a discovery is shown (Live Discovery, search, knowledge details).
 */
export function Insight({
  label = 'Discovered knowledge',
  badges,
  title,
  children,
  className,
}: {
  label?: string
  badges?: ReactNode
  title: ReactNode
  children?: ReactNode
  className?: string
}) {
  return (
    <div className={cn('rounded-lg border border-insight-border bg-insight p-4', className)}>
      <div className="mb-2 flex flex-wrap items-center gap-x-2 gap-y-1.5">
        <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-insight-foreground">
          <Sparkles className="size-3.5" aria-hidden="true" />
          {label}
        </span>
        {badges && <span className="flex flex-wrap items-center gap-1.5">{badges}</span>}
      </div>
      <h3 className="text-[17px] leading-snug font-semibold text-foreground text-balance">
        {title}
      </h3>
      {children && <div className="mt-3 flex flex-col gap-3">{children}</div>}
    </div>
  )
}
