import { Workflow } from 'lucide-react'

import { PlannedFeature } from '@/components/PlannedFeature'
import { Card, CardContent } from '@/components/ui/card'

const journeySteps = [
  { title: 'Describe the problem', text: 'Symptoms, affected equipment and alarms.' },
  { title: 'Follow the decision tree', text: 'Answer questions and record observations.' },
  { title: 'Review the evidence', text: 'See incidents, documents and experts behind each step.' },
  { title: 'Record the resolution', text: 'Save the journey so the next engineer benefits.' },
]

export default function Troubleshoot() {
  return (
    <PlannedFeature
      icon={Workflow}
      title="Guided Troubleshooting"
      description="Interactive decision trees built from the knowledge of experienced engineers, with the evidence behind every step."
      capabilities={[
        'Evidence-backed troubleshooting decision trees',
        'Supporting incidents, documents and experts per step',
        'Approval status and applicability conditions',
        'Alternative paths combined from multiple experts',
      ]}
    >
      <Card>
        <CardContent>
          <h2 className="mb-4 text-sm font-medium text-foreground">
            How a troubleshooting session will work
          </h2>
          <ol className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {journeySteps.map((step, index) => (
              <li key={step.title} className="flex gap-3">
                <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground">
                  {index + 1}
                </span>
                <div>
                  <p className="text-sm font-medium text-foreground">{step.title}</p>
                  <p className="text-sm text-muted-foreground">{step.text}</p>
                </div>
              </li>
            ))}
          </ol>
        </CardContent>
      </Card>
    </PlannedFeature>
  )
}
