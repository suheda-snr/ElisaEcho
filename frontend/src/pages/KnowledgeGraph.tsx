import { Background, Controls, ReactFlow, type Edge, type Node } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { Network } from 'lucide-react'

import { PlannedFeature } from '@/components/PlannedFeature'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

// A schematic of the planned entity model, not real data.
const nodes: Node[] = [
  { id: 'knowledge', position: { x: 330, y: 0 }, data: { label: 'Knowledge item' } },
  { id: 'equipment', position: { x: 0, y: 200 }, data: { label: 'Equipment' } },
  { id: 'incident', position: { x: 220, y: 200 }, data: { label: 'Incident' } },
  { id: 'event', position: { x: 440, y: 200 }, data: { label: 'Network event' } },
  { id: 'expert', position: { x: 660, y: 200 }, data: { label: 'Expert' } },
]

const edges: Edge[] = [
  { id: 'k-equipment', source: 'knowledge', target: 'equipment', label: 'applies to' },
  { id: 'k-incident', source: 'knowledge', target: 'incident', label: 'resolved' },
  { id: 'k-event', source: 'knowledge', target: 'event', label: 'explains' },
  { id: 'k-expert', source: 'knowledge', target: 'expert', label: 'contributed by' },
]

export default function KnowledgeGraph() {
  return (
    <PlannedFeature
      icon={Network}
      title="Knowledge Graph"
      description="Explore how knowledge connects equipment, incidents, network events and the experts behind them."
      capabilities={[
        'Interactive graph of captured knowledge',
        'Navigate from equipment to related incidents',
        'See which experts contributed to each topic',
        'Spot gaps where knowledge is missing',
      ]}
    >
      <Card>
        <CardHeader>
          <CardTitle>Planned data model</CardTitle>
          <CardDescription>
            A schematic of the entities the graph will connect. It contains no real data.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="h-96 w-full overflow-hidden rounded-lg border bg-background">
            <ReactFlow nodes={nodes} edges={edges} fitView nodesConnectable={false}>
              <Background />
              <Controls showInteractive={false} />
            </ReactFlow>
          </div>
        </CardContent>
      </Card>
    </PlannedFeature>
  )
}
