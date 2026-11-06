import { FileAudio, FileImage, FileText, FileVideo, NotebookPen, Upload } from 'lucide-react'

import { PlannedFeature } from '@/components/PlannedFeature'
import { Card, CardContent } from '@/components/ui/card'

const sourceTypes = [
  { label: 'Text notes', icon: NotebookPen },
  { label: 'Audio recordings', icon: FileAudio },
  { label: 'Video', icon: FileVideo },
  { label: 'Images', icon: FileImage },
  { label: 'PDF documents', icon: FileText },
]

export default function Capture() {
  return (
    <PlannedFeature
      icon={Upload}
      title="Capture Knowledge"
      description="Engineers will contribute what they know — from quick notes to recorded walkthroughs — and Elisa Echo will turn it into structured operational knowledge."
      capabilities={[
        'Upload text, audio, video, images and PDF documents',
        'Automatic transcription and knowledge extraction',
        'Link knowledge to equipment, incidents and network events',
        'Attribute contributions to experts for review and approval',
      ]}
    >
      <Card>
        <CardContent>
          <h2 className="mb-3 text-sm font-medium text-foreground">Supported sources</h2>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
            {sourceTypes.map(({ label, icon: Icon }) => (
              <div
                key={label}
                className="flex flex-col items-center gap-2 rounded-lg border border-dashed px-3 py-5 text-center text-sm text-muted-foreground"
              >
                <Icon className="size-6" aria-hidden="true" />
                {label}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </PlannedFeature>
  )
}
