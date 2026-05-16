import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { agentApi, taskApi, clusterApi } from '../api/http_client_configuration';

export const queryKeys = {
  agents: ['agents'] as const,
  agent: (id: string) => ['agents', id] as const,
  agentStats: ['agentStats'] as const,
  agentCapabilities: ['agentCapabilities'] as const,
  tasks: ['tasks'] as const,
  task: (id: string) => ['tasks', id] as const,
  clusterStats: ['clusterStats'] as const,
  health: ['health'] as const,
};

export function useAgents(page = 1, pageSize = 20) {
  return useQuery({
    queryKey: [...queryKeys.agents, page, pageSize],
    queryFn: () => agentApi.list(page, pageSize),
    refetchInterval: 5000,
  });
}

export function useAgent(id: string) {
  return useQuery({
    queryKey: queryKeys.agent(id),
    queryFn: () => agentApi.get(id),
    enabled: !!id,
  });
}

export function useAgentStats() {
  return useQuery({
    queryKey: queryKeys.agentStats,
    queryFn: agentApi.stats,
    refetchInterval: 10000,
  });
}

export function useAgentCapabilities() {
  return useQuery({
    queryKey: queryKeys.agentCapabilities,
    queryFn: agentApi.capabilities,
  });
}

export function useCreateAgent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (agent: any) => agentApi.create(agent),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.agents });
      queryClient.invalidateQueries({ queryKey: queryKeys.agentStats });
      queryClient.invalidateQueries({ queryKey: queryKeys.agentCapabilities });
    },
  });
}

export function useUpdateAgent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...agent }: any) => agentApi.update(id, agent),
    onSuccess: ( _data, variables) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.agents });
      queryClient.invalidateQueries({ queryKey: queryKeys.agent(variables.id) });
    },
  });
}

export function useDeleteAgent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => agentApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.agents });
      queryClient.invalidateQueries({ queryKey: queryKeys.agentStats });
      queryClient.invalidateQueries({ queryKey: queryKeys.agentCapabilities });
    },
  });
}

export function useTasks(page = 1, pageSize = 20, status?: string) {
  return useQuery({
    queryKey: [...queryKeys.tasks, page, pageSize, status],
    queryFn: () => taskApi.list(page, pageSize, status),
    refetchInterval: 3000,
  });
}

export function useTask(id: string) {
  return useQuery({
    queryKey: queryKeys.task(id),
    queryFn: () => taskApi.get(id),
    enabled: !!id,
    refetchInterval: 2000,
  });
}

export function useCreateTask() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (task: { description: string; priority?: number }) => taskApi.create(task),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.tasks });
      queryClient.invalidateQueries({ queryKey: queryKeys.clusterStats });
    },
  });
}

export function useCancelTask() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => taskApi.cancel(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.tasks });
    },
  });
}

export function useClusterStats() {
  return useQuery({
    queryKey: queryKeys.clusterStats,
    queryFn: clusterApi.stats,
    refetchInterval: 5000,
  });
}

export function useExecuteClusterTask() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ description, numAgents }: { description: string; numAgents: number }) =>
      clusterApi.execute(description, numAgents),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.tasks });
      queryClient.invalidateQueries({ queryKey: queryKeys.clusterStats });
    },
  });
}
