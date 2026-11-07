import {
  Background,
  Controls,
  Handle,
  MarkerType,
  Position,
  ReactFlow,
  type Edge,
  type Node,
  type NodeProps,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { MessageSquareQuote, ShieldAlert } from 'lucide-react'
import { useMemo } from 'react'

import { layoutGuide, NODE_WIDTH } from '@/components/troubleshooting/layout'
import { nodeTypeStyle, supportStyle } from '@/components/troubleshooting/nodeStyles'
import { cn } from '@/lib/utils'
import type { Guide, GuideNode } from '@/types/api'

type StepNodeData = {
  node: GuideNode
  active: boolean
  onPath: boolean
  selected: boolean
}

function StepNode({ data }: NodeProps<Node<StepNodeData>>) {
  const { node, active, onPath, selected } = data
  const style = nodeTypeStyle[node.node_type]
  const support = supportStyle[node.support_level]
  const Icon = style.icon
  return (
    <div
      className={cn(
        'rounded-lg border border-l-4 bg-card px-3 py-2 text-left shadow-sm transition-shadow',
        style.accent,
        onPath && 'bg-accent',
        selected && 'ring-2 ring-ring/60',
        active && 'shadow-md ring-2 ring-primary',
      )}
      style={{ width: NODE_WIDTH }}
    >
      <Handle type="target" position={Position.Top} className="!bg-muted-foreground" />
      <div className="mb-1 flex items-center gap-1.5">
        <span
          className={cn(
            'inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-medium',
            style.chip,
          )}
        >
          <Icon className="size-3" aria-hidden="true" />
          {style.label}
        </span>
        {active && (
          <span className="text-[10px] font-semibold text-primary uppercase">Current</span>
        )}
      </div>
      <p className="text-xs leading-snug font-medium text-foreground">{node.title}</p>
      <div className="mt-1.5 flex flex-wrap items-center gap-1">
        {support && (
          <span className={cn('rounded border px-1 text-[10px]', support.className)}>
            {support.label}
          </span>
        )}
        {node.evidence.length > 0 && (
          <span className="inline-flex items-center gap-0.5 text-[10px] text-muted-foreground">
            <MessageSquareQuote className="size-3" aria-hidden="true" />
            {node.evidence.length}
          </span>
        )}
        {node.requires_manual_verification && (
          <ShieldAlert
            className="size-3 text-amber-600"
            aria-label="Requires manual verification"
          />
        )}
      </div>
      <Handle type="source" position={Position.Bottom} className="!bg-muted-foreground" />
    </div>
  )
}

const nodeTypes = { step: StepNode }

interface GuideFlowProps {
  guide: Guide
  activePath: string[]
  currentNodeId: string | null
  selectedNodeId: string | null
  onSelect: (nodeId: string) => void
}

export function GuideFlow({
  guide,
  activePath,
  currentNodeId,
  selectedNodeId,
  onSelect,
}: GuideFlowProps) {
  const positions = useMemo(() => layoutGuide(guide), [guide])
  const onPath = useMemo(() => new Set(activePath), [activePath])
  const pathEdges = useMemo(() => {
    const pairs = new Set<string>()
    for (let i = 1; i < activePath.length; i++) pairs.add(`${activePath[i - 1]}>${activePath[i]}`)
    return pairs
  }, [activePath])

  const nodes: Node<StepNodeData>[] = guide.nodes.map((n) => ({
    id: n.id,
    type: 'step',
    position: positions.get(n.id) ?? { x: 0, y: 0 },
    data: {
      node: n,
      active: n.id === currentNodeId,
      onPath: onPath.has(n.id),
      selected: n.id === selectedNodeId,
    },
    draggable: false,
  }))

  const edges: Edge[] = guide.edges.map((e) => {
    const taken = pathEdges.has(`${e.source_node_id}>${e.target_node_id}`)
    return {
      id: e.id,
      source: e.source_node_id,
      target: e.target_node_id,
      label: e.answer_label,
      animated: taken,
      markerEnd: { type: MarkerType.ArrowClosed },
      style: {
        stroke: taken ? 'var(--primary)' : 'var(--muted-foreground)',
        strokeWidth: taken ? 2.5 : 1.2,
      },
      labelStyle: { fontSize: 11, fill: 'var(--foreground)' },
      labelBgStyle: { fill: 'var(--card)' },
    }
  })

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      fitView
      fitViewOptions={{ padding: 0.15 }}
      minZoom={0.3}
      nodesConnectable={false}
      onNodeClick={(_, node) => onSelect(node.id)}
    >
      <Background />
      <Controls showInteractive={false} />
    </ReactFlow>
  )
}
