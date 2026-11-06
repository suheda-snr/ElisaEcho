import { AudioWaveform } from 'lucide-react'

export function Brand() {
  return (
    <div className="flex items-center gap-2.5">
      <span className="flex size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
        <AudioWaveform className="size-4" aria-hidden="true" />
      </span>
      <span className="flex flex-col leading-tight">
        <span className="text-sm font-semibold text-foreground">Elisa Echo</span>
        <span className="text-xs text-muted-foreground">Operational knowledge</span>
      </span>
    </div>
  )
}
