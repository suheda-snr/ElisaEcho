import { NavLink } from 'react-router'

import { cn } from '@/lib/utils'
import { navItems, type NavItem } from '@/lib/navigation'

interface SidebarNavProps {
  onNavigate?: () => void
}

const GROUPS: { key: NavItem['group']; label: string | null }[] = [
  { key: 'overview', label: null },
  { key: 'workflow', label: 'Workflow' },
  { key: 'setup', label: 'Setup' },
  { key: 'planned', label: 'Coming next' },
]

export function SidebarNav({ onNavigate }: SidebarNavProps) {
  return (
    <nav aria-label="Main navigation" className="flex flex-col gap-5">
      {GROUPS.filter((group) => navItems.some((item) => item.group === group.key)).map((group) => (
        <div key={group.key} className="flex flex-col gap-1">
          {group.label && (
            <p className="px-3 pb-1 text-[11px] font-semibold tracking-wider text-muted-foreground uppercase">
              {group.label}
            </p>
          )}
          {navItems
            .filter((item) => item.group === group.key)
            .map(({ to, label, icon: Icon, step, group: kind }) => (
              <NavLink
                key={to}
                to={to}
                end={to === '/'}
                onClick={onNavigate}
                className={({ isActive }) =>
                  cn(
                    'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                    'focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none',
                    isActive
                      ? 'bg-sidebar-accent text-sidebar-accent-foreground'
                      : 'text-muted-foreground hover:bg-sidebar-accent/60 hover:text-sidebar-foreground',
                    kind === 'planned' && !isActive && 'opacity-70',
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    {step ? (
                      <span
                        className={cn(
                          'flex size-5 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold',
                          isActive
                            ? 'bg-primary text-primary-foreground'
                            : 'bg-muted text-muted-foreground',
                        )}
                        aria-hidden="true"
                      >
                        {step}
                      </span>
                    ) : (
                      <Icon className="size-4 shrink-0" aria-hidden="true" />
                    )}
                    <span className="min-w-0 flex-1 truncate">{label}</span>
                    {kind === 'planned' && (
                      <span className="rounded bg-muted px-1.5 text-[10px] font-medium text-muted-foreground">
                        Planned
                      </span>
                    )}
                  </>
                )}
              </NavLink>
            ))}
        </div>
      ))}
    </nav>
  )
}
