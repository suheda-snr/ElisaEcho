import {
  BookOpenText,
  Cable,
  LayoutDashboard,
  Network,
  Radar,
  Search,
  Workflow,
  type LucideIcon,
} from 'lucide-react'

export interface NavItem {
  to: string
  label: string
  /** One sentence shown under the page title and on the dashboard. */
  description: string
  icon: LucideIcon
  group: 'overview' | 'workflow' | 'setup' | 'planned'
  /** Position in the end-to-end workflow (shown as a number). */
  step?: number
}

/** Ordered like the product workflow: discover -> store -> find -> act. */
export const navItems: NavItem[] = [
  {
    to: '/',
    label: 'Overview',
    description: 'How Elisa Echo works, live metrics and system status.',
    icon: LayoutDashboard,
    group: 'overview',
  },
  {
    to: '/discovery',
    label: 'Live Discovery',
    description: 'Watch AI find operational knowledge in engineers’ conversations as they happen.',
    icon: Radar,
    group: 'workflow',
    step: 1,
  },
  {
    to: '/knowledge',
    label: 'Knowledge Base',
    description: 'Every piece of discovered knowledge, with the messages that prove it.',
    icon: BookOpenText,
    group: 'workflow',
    step: 2,
  },
  {
    to: '/search',
    label: 'Search',
    description: 'Describe a problem in your own words and find how colleagues solved it.',
    icon: Search,
    group: 'workflow',
    step: 3,
  },
  {
    to: '/troubleshoot',
    label: 'Guided Troubleshooting',
    description: 'A step-by-step decision tree built only from evidence, saved as a session.',
    icon: Workflow,
    group: 'workflow',
    step: 4,
  },
  {
    to: '/integrations',
    label: 'Integrations',
    description:
      'Connect authorized Slack channels so knowledge is discovered from real conversations.',
    icon: Cable,
    group: 'setup',
  },
  {
    to: '/graph',
    label: 'Knowledge Graph',
    description: 'Relationships between equipment, incidents and experts.',
    icon: Network,
    group: 'planned',
  },
]

export function navItemFor(pathname: string): NavItem | undefined {
  return navItems.find((item) =>
    item.to === '/' ? pathname === '/' : pathname.startsWith(item.to),
  )
}
