import { BackendStatus } from '@/components/BackendStatus'
import { Brand } from '@/components/layout/Brand'
import { SidebarNav } from '@/components/layout/SidebarNav'

/** Persistent sidebar, visible from the `lg` breakpoint upwards. */
export function Sidebar() {
  return (
    <aside className="sticky top-0 hidden h-dvh w-60 shrink-0 flex-col border-r border-sidebar-border bg-sidebar lg:flex">
      <div className="flex h-16 items-center px-4">
        <Brand />
      </div>
      <div className="flex-1 overflow-y-auto px-3 py-2">
        <SidebarNav />
      </div>
      <div className="px-4 pb-4">
        <BackendStatus />
      </div>
    </aside>
  )
}
