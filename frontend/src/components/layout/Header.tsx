import { Menu } from 'lucide-react'
import { useState } from 'react'

import { BackendStatus } from '@/components/BackendStatus'
import { Brand } from '@/components/layout/Brand'
import { SidebarNav } from '@/components/layout/SidebarNav'
import { Button } from '@/components/ui/button'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet'

/** Slim top bar: mobile menu, breadcrumb and connection status. Page titles live in PageHeader. */
export function Header() {
  const [menuOpen, setMenuOpen] = useState(false)

  return (
    <header className="sticky top-0 z-30 flex h-20 shrink-0 items-center gap-3 border-b bg-background/95 px-4 backdrop-blur sm:px-6">
      <Sheet open={menuOpen} onOpenChange={setMenuOpen}>
        <SheetTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            className="lg:hidden"
            aria-label="Open navigation menu"
          >
            <Menu />
          </Button>
        </SheetTrigger>
        <SheetContent side="left" className="w-72 gap-0 bg-sidebar p-0">
          <SheetHeader className="h-20 items-center justify-center border-b border-sidebar-border px-5">
            <SheetTitle className="sr-only">Navigation</SheetTitle>
            <SheetDescription className="sr-only">Elisa Echo main navigation</SheetDescription>
            <Brand />
          </SheetHeader>
          <div className="p-3">
            <SidebarNav onNavigate={() => setMenuOpen(false)} />
          </div>
        </SheetContent>
      </Sheet>

      {/* Page titles live in PageHeader; the top bar only holds the menu and status. */}
      <div className="flex-1" />

      <BackendStatus />
    </header>
  )
}
