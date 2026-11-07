import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { getSlackChannels, getSlackEvents, getSlackStatus, setSlackChannel } from '@/services/api'

export function useSlackStatus() {
  return useQuery({ queryKey: ['slack', 'status'], queryFn: getSlackStatus, refetchInterval: 5000 })
}

export function useSlackChannels(enabled: boolean) {
  return useQuery({
    queryKey: ['slack', 'channels'],
    queryFn: getSlackChannels,
    enabled,
    refetchInterval: 30_000,
  })
}

export function useSlackEvents() {
  return useQuery({ queryKey: ['slack', 'events'], queryFn: getSlackEvents, refetchInterval: 5000 })
}

export function useSetSlackChannel() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ channelId, enabled }: { channelId: string; enabled: boolean }) =>
      setSlackChannel(channelId, enabled),
    onSettled: () => void client.invalidateQueries({ queryKey: ['slack'] }),
  })
}
