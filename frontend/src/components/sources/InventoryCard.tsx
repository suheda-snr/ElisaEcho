import { Server } from 'lucide-react'

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useInventory } from '@/hooks/useSources'
import { getErrorMessage } from '@/services/api'

/** Synthetic network inventory: the entities knowledge is bound to. */
export function InventoryCard() {
  const inventory = useInventory()
  const data = inventory.data
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Server className="size-4" aria-hidden="true" />
          Network inventory
        </CardTitle>
        <CardDescription>
          Knowledge is bound to these nodes, their unit class and their site. A fix learned on one
          node that “applies to these older units” is found for its siblings too.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3 text-sm">
        {inventory.isError && <p className="text-red-700">{getErrorMessage(inventory.error)}</p>}
        {data && data.nodes.length === 0 && (
          <p className="text-muted-foreground">
            The synthetic inventory is loaded when the live demo starts.
          </p>
        )}
        {data && data.nodes.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="text-muted-foreground">
                <tr>
                  <th className="py-1 pr-3 font-medium">Node</th>
                  <th className="py-1 pr-3 font-medium">Unit class</th>
                  <th className="py-1 pr-3 font-medium">Installed</th>
                  <th className="py-1 pr-3 font-medium">Site</th>
                  <th className="py-1 text-right font-medium">Knowledge</th>
                </tr>
              </thead>
              <tbody>
                {data.nodes.map((n) => (
                  <tr key={n.equipment_identifier} className="border-t">
                    <td className="py-1.5 pr-3 font-mono">{n.equipment_identifier}</td>
                    <td className="py-1.5 pr-3">{n.unit_class}</td>
                    <td className="py-1.5 pr-3 tabular-nums">{n.installed_year ?? '–'}</td>
                    <td className="py-1.5 pr-3 font-mono">{n.site_identifier}</td>
                    <td className="py-1.5 text-right tabular-nums" title="direct / via unit class">
                      {n.knowledge_count} / {n.class_knowledge_count}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {data && data.sites.length > 0 && (
          <ul className="flex flex-col gap-1">
            {data.sites
              .filter((s) => s.knowledge_count > 0 || s.description)
              .map((s) => (
                <li key={s.site_identifier} className="text-xs text-muted-foreground">
                  <span className="font-mono text-foreground">{s.site_identifier}</span> {s.name} ·{' '}
                  {s.region} · {s.knowledge_count} knowledge item(s)
                </li>
              ))}
          </ul>
        )}
        {data && <p className="text-xs text-muted-foreground">{data.note}</p>}
      </CardContent>
    </Card>
  )
}
