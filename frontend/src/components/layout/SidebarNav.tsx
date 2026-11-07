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
    <nav aria-label="Main navigation" className="flex flex-col">
      {groups.map((items, index) => (
        <div
          key={index}
          className={cn(
            'flex flex-col gap-0.5',
            index > 0 && 'mt-4 border-t border-sidebar-border pt-4',
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
                  'group flex h-9 items-center gap-2.5 rounded-md px-2.5 text-sm transition-colors duration-150',
                  'focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none',
                  isActive
                    ? 'bg-sidebar-accent font-medium text-sidebar-accent-foreground'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                )
              }
            >
              <Icon className="size-4 shrink-0" aria-hidden="true" />
              <span className="min-w-0 flex-1 truncate">{label}</span>
            </NavLink>
          ))}
        </div>
      ))}
    </nav>
  )
}
