import { cn } from '@/lib/utils'
import { useHealth } from '@/hooks/useHealth'

type Status = 'connected' | 'connecting' | 'unavailable'

const statusStyles: Record<Status, { label: string; dot: string; text: string }> = {
  connected: { label: 'Backend connected', dot: 'bg-emerald-500', text: 'text-emerald-700' },
  connecting: { label: 'Connecting', dot: 'bg-amber-500 animate-pulse', text: 'text-amber-700' },
  unavailable: { label: 'Backend unavailable', dot: 'bg-red-500', text: 'text-red-700' },
}

/** Compact live indicator of the API connection, driven by GET /api/health. */
export function BackendStatus({ className }: { className?: string }) {
  const { isPending, isError } = useHealth()
  const status: Status = isPending ? 'connecting' : isError ? 'unavailable' : 'connected'
  const style = statusStyles[status]

  return (
    <span
      role="status"
      className={cn(
        'inline-flex items-center gap-2 rounded-full border bg-background px-3 py-1 text-xs font-medium',
        style.text,
        className,
      )}
    >
      <span className={cn('size-2 rounded-full', style.dot)} aria-hidden="true" />
      {style.label}
    </span>
  )
}
