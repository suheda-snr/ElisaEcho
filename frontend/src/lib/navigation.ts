import { LayoutDashboard, Network, Radar, Search, Workflow, type LucideIcon } from 'lucide-react'

export interface NavItem {
  to: string
  label: string
  description: string
  icon: LucideIcon
}

export const navItems: NavItem[] = [
  {
    to: '/',
    label: 'Dashboard',
    description: 'Platform overview and system status',
    icon: LayoutDashboard,
  },
  {
    to: '/discovery',
    label: 'Live Discovery',
    description: 'Knowledge discovered automatically from engineer conversations',
    icon: Radar,
  },
  {
    to: '/search',
    label: 'Search Knowledge',
    description: 'Find incidents, procedures and expert insights',
    icon: Search,
  },
  {
    to: '/troubleshoot',
    label: 'Guided Troubleshooting',
    description: 'Step-by-step, evidence-backed decision trees',
    icon: Workflow,
  },
  {
    to: '/graph',
    label: 'Knowledge Graph',
    description: 'Relationships between equipment, incidents and experts',
    icon: Network,
  },
]
