import axios from 'axios';
import type { Agent, ClusterStats } from '../types/application_type_definitions';

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API Error:', error.response?.data || error.message);
    return Promise.reject(error);
  }
);

export const agentApi = {
  list: async (page = 1, pageSize = 20) => {
    const { data } = await api.get('/agents', { params: { page, page_size: pageSize } });
    return data;
  },

  get: async (id: string) => {
    const { data } = await api.get(`/agents/${id}`);
    return data;
  },

  create: async (agent: Partial<Agent>) => {
    const { data } = await api.post('/agents', agent);
    return data;
  },

  update: async (id: string, agent: Partial<Agent>) => {
    const { data } = await api.patch(`/agents/${id}`, agent);
    return data;
  },

  delete: async (id: string) => {
    await api.delete(`/agents/${id}`);
  },

  heartbeat: async (id: string) => {
    await api.post(`/agents/${id}/heartbeat`);
  },

  stats: async () => {
    const { data } = await api.get('/agents/stats');
    return data;
  },

  capabilities: async () => {
    const { data } = await api.get('/agents/capabilities');
    return data;
  },
};

export const taskApi = {
  list: async (page = 1, pageSize = 20, status?: string) => {
    const { data } = await api.get('/tasks', { 
      params: { page, page_size: pageSize, status } 
    });
    return data;
  },

  get: async (id: string) => {
    const { data } = await api.get(`/tasks/${id}`);
    return data;
  },

  create: async (task: { description: string; priority?: number }) => {
    const { data } = await api.post('/tasks', task);
    return data;
  },

  cancel: async (id: string) => {
    await api.delete(`/tasks/${id}`);
  },

  result: async (id: string) => {
    const { data } = await api.get(`/tasks/${id}/result`);
    return data;
  },
};

export const clusterApi = {
  stats: async (): Promise<ClusterStats> => {
    const { data } = await api.get('/cluster/stats');
    return data;
  },

  execute: async (description: string, numAgents: number) => {
    const { data } = await api.post('/cluster/execute', {
      description,
      num_agents: numAgents,
    });
    return data;
  },
};

export const healthApi = {
  check: async () => {
    const { data } = await api.get('/health');
    return data;
  },

  ready: async () => {
    const { data } = await api.get('/ready');
    return data;
  },
};

export default api;
