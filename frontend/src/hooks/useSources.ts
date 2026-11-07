import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  checkMailbox,
  connectMailbox,
  disconnectMailbox,
  getEmailConnections,
  getInventory,
  setMailboxEnabled,
} from '@/services/api'
import type { EmailConnectionCreate } from '@/types/api'

export function useInventory() {
  return useQuery({ queryKey: ['inventory'], queryFn: getInventory, refetchInterval: 30_000 })
}

export function useEmailConnections() {
  return useQuery({
    queryKey: ['email', 'connections'],
    queryFn: getEmailConnections,
    refetchInterval: 10_000,
  })
}

export function useMailboxActions() {
  const client = useQueryClient()
  const done = () => {
    void client.invalidateQueries({ queryKey: ['email'] })
    void client.invalidateQueries({ queryKey: ['discovery'] })
  }
  return {
    connect: useMutation({
      mutationFn: (body: EmailConnectionCreate) => connectMailbox(body),
      onSuccess: done,
    }),
    check: useMutation({ mutationFn: (id: string) => checkMailbox(id), onSuccess: done }),
    toggle: useMutation({
      mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
        setMailboxEnabled(id, enabled),
      onSuccess: done,
    }),
    disconnect: useMutation({ mutationFn: (id: string) => disconnectMailbox(id), onSuccess: done }),
  }
}
