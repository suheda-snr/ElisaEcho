import {
  BookOpenText,
  Cable,
  LayoutDashboard,
  Radar,
  Workflow,
  type LucideIcon,
} from 'lucide-react'

export interface NavItem {
  to: string
  label: string
  /** One short sentence under the page title. */
  description: string
  icon: LucideIcon
  group: 'main' | 'setup'
  /** Other paths that belong to this page (old routes, sub-views). */
  matches?: string[]
}

export const navItems: NavItem[] = [
  {
    to: '/',
    label: 'Overview',
    description: 'What Elisa Echo has captured from your conversations.',
    icon: LayoutDashboard,
    group: 'main',
  },
  {
    to: '/discovery',
    label: 'Live Discovery',
    description: 'Conversations as they arrive, and the context the AI found in them.',
    icon: Radar,
    group: 'main',
  },
  {
    to: '/knowledge',
    label: 'Knowledge Explorer',
    description: 'Search, browse and compare everything that was discovered.',
    icon: BookOpenText,
    group: 'main',
    matches: ['/search', '/network'],
  },
  {
    to: '/troubleshoot',
    label: 'Troubleshooting',
    description: 'Step-by-step guidance built from discovered knowledge.',
    icon: Workflow,
    group: 'main',
  },
  {
    to: '/integrations',
    label: 'Integrations',
    description: 'Where knowledge is captured from.',
    icon: Cable,
    group: 'setup',
  },
]

export function navItemFor(pathname: string): NavItem | undefined {
  return navItems.find((item) =>
    item.to === '/'
      ? pathname === '/'
      : [item.to, ...(item.matches ?? [])].some((p) => pathname.startsWith(p)),
  )
}
