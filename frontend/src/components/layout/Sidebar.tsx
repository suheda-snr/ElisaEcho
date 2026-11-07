import { Brand } from '@/components/layout/Brand'
import { SidebarNav } from '@/components/layout/SidebarNav'

/** Persistent sidebar, visible from the `lg` breakpoint upwards. */
export function Sidebar() {
  return (
    <aside className="hidden w-64 shrink-0 flex-col border-r border-sidebar-border bg-sidebar lg:flex">
      <div className="flex h-16 items-center border-b border-sidebar-border px-5">
        <Brand />
      </div>
      <div className="flex-1 overflow-y-auto p-3">
        <SidebarNav />
      </div>
      <div className="border-t border-sidebar-border px-5 py-4 text-xs text-muted-foreground">
        Phase 5 · Guided troubleshooting
      </div>
    </aside>
  )
}
