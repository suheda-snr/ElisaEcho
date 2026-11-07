import type { Guide } from '@/types/api'

export const NODE_WIDTH = 230
const X_GAP = 40
const Y_GAP = 140

/** Deterministic layered layout: level = longest path from the start; order by position. */
export function layoutGuide(guide: Guide): Map<string, { x: number; y: number }> {
  const children = new Map<string, string[]>()
  for (const e of guide.edges) {
    children.set(e.source_node_id, [...(children.get(e.source_node_id) ?? []), e.target_node_id])
  }
  const level = new Map<string, number>()
  const visit = (id: string, depth: number) => {
    if ((level.get(id) ?? -1) >= depth) return
    level.set(id, depth)
    for (const child of children.get(id) ?? []) visit(child, depth + 1)
  }
  if (guide.start_node_id) visit(guide.start_node_id, 0)
  guide.nodes.forEach((n) => {
    if (!level.has(n.id)) level.set(n.id, 0)
  })

  const rows = new Map<number, string[]>()
  for (const n of guide.nodes) {
    const l = level.get(n.id) ?? 0
    rows.set(l, [...(rows.get(l) ?? []), n.id])
  }
  const positions = new Map<string, { x: number; y: number }>()
  for (const [l, ids] of rows) {
    const width = ids.length * NODE_WIDTH + (ids.length - 1) * X_GAP
    ids.forEach((id, i) =>
      positions.set(id, { x: i * (NODE_WIDTH + X_GAP) - width / 2, y: l * Y_GAP }),
    )
  }
  return positions
}
