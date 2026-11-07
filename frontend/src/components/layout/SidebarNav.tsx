import { NavLink } from 'react-router'

import { navItems } from '@/lib/navigation'
import { cn } from '@/lib/utils'

interface SidebarNavProps {
  onNavigate?: () => void
}

export function SidebarNav({ onNavigate }: SidebarNavProps) {
  const groups = [
    navItems.filter((i) => i.group === 'main'),
    navItems.filter((i) => i.group === 'setup'),
  ]
  return (
    <nav aria-label="Main navigation" className="flex flex-col gap-1">
      {groups.map((items, index) => (
        <div
          key={index}
          className={cn(
            'flex flex-col gap-1',
            index > 0 && 'mt-3 border-t border-sidebar-border pt-3',
          )}
        >
          {items.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              onClick={onNavigate}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors',
                  'focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none',
                  isActive
                    ? 'bg-sidebar-accent text-sidebar-accent-foreground'
                    : 'text-foreground/75 hover:bg-sidebar-accent/60 hover:text-sidebar-foreground',
                )
              }
            >
              <Icon className="size-[18px] shrink-0" aria-hidden="true" />
              <span className="min-w-0 flex-1 truncate">{label}</span>
            </NavLink>
          ))}
        </div>
      ))}
    </nav>
  )
}
