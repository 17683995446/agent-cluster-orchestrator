export interface Agent {
  id: string;
  name: string;
  capabilities: string[];
  status: 'idle' | 'busy' | 'offline';
  model: string;
  provider: 'openai' | 'anthropic' | 'local';
  current_task: string | null;
  stats: {
    total_tasks: number;
    success_count: number;
    failure_count: number;
    total_response_time: number;
  };
  created_at: string;
  last_heartbeat: string;
}

export interface Task {
  id: string;
  type: 'single' | 'composite';
  description: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  assigned_agent: string | null;
  subtasks: string[];
  parent_task: string | null;
  result: any | null;
  error: string | null;
  priority: number;
  retry_count: number;
  max_retries: number;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface ClusterStats {
  total_agents: number;
  active_agents: number;
  idle_agents: number;
  busy_agents: number;
  offline_agents: number;
  total_tasks: number;
  pending_tasks: number;
  running_tasks: number;
  completed_tasks: number;
  failed_tasks: number;
  success_rate: number;
  avg_response_time: number;
}

export interface PaginationInfo {
  items: any[];
  total: number;
  page: number;
  page_size: number;
}
