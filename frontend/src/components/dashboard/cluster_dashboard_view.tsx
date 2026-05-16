import { useState } from 'react';
import { 
  Cpu, Activity, CheckCircle, XCircle, Clock, AlertCircle,
  Plus, RefreshCw, Trash2, Play, Layers
} from 'lucide-react';
import { Card, CardHeader, CardTitle, CardContent } from '../ui/ui_card_container_component';
import { Button } from '../ui/ui_button_component';
import { Input } from '../ui/ui_input_component';
import { Badge } from '../ui/ui_status_badge_component';
import { Modal } from '../ui/ui_modal_dialog_component';
import { 
  useAgents, useAgentStats, useTasks, useClusterStats,
  useCreateAgent, useDeleteAgent, useCreateTask, useExecuteClusterTask
} from '../../hooks/use_agent_cluster_hooks';
import type { Agent, Task } from '../../types/application_type_definitions';

const statusColors = {
  idle: { bg: 'bg-success-500/10', text: 'text-success-500', border: 'border-success-500' },
  busy: { bg: 'bg-warning-500/10', text: 'text-warning-500', border: 'border-warning-500' },
  offline: { bg: 'bg-slate-500/10', text: 'text-slate-400', border: 'border-slate-500' },
};

const taskStatusColors = {
  pending: 'info',
  running: 'warning',
  completed: 'success',
  failed: 'danger',
  cancelled: 'default',
} as const;

export function Dashboard() {
  const [activeTab, setActiveTab] = useState<'agents' | 'tasks' | 'console'>('agents');
  const [showAgentModal, setShowAgentModal] = useState(false);
  const [agentForm, setAgentForm] = useState({
    name: '',
    capabilities: [] as string[],
    model: 'gpt-4',
    provider: 'openai',
  });
  const [taskDescription, setTaskDescription] = useState('');
  const [priority, setPriority] = useState(0);
  const [clusterDescription, setClusterDescription] = useState('');
  const [numAgents, setNumAgents] = useState(3);

  const { data: agentsData, refetch: refetchAgents } = useAgents();
  const { refetch: refetchStats } = useAgentStats();
  const { data: tasksData, refetch: refetchTasks } = useTasks();
  const { data: clusterStats, refetch: refetchCluster } = useClusterStats();

  const createAgent = useCreateAgent();
  const deleteAgent = useDeleteAgent();
  const createTask = useCreateTask();
  const executeClusterTask = useExecuteClusterTask();

  const agents = agentsData?.items || [];
  const tasks = tasksData?.items || [];

  const handleCreateAgent = async () => {
    await createAgent.mutateAsync(agentForm);
    setShowAgentModal(false);
    setAgentForm({ name: '', capabilities: [], model: 'gpt-4', provider: 'openai' });
  };

  const handleCreateTask = async () => {
    await createTask.mutateAsync({ description: taskDescription, priority });
    setTaskDescription('');
    setPriority(0);
  };

  const handleExecuteCluster = async () => {
    await executeClusterTask.mutateAsync({ description: clusterDescription, numAgents });
    setClusterDescription('');
  };

  const capabilities = ['code_generation', 'code_review', 'data_analysis', 'writing', 'translation', 'summarization'];

  return (
    <div className="min-h-screen bg-slate-900">
      <header className="bg-slate-800 border-b border-slate-700 px-6 py-4">
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-2xl font-bold text-white">Agent Cluster Orchestrator</h1>
            <p className="text-sm text-slate-400">分布式智能Agent集群管理系统</p>
          </div>
          <div className="flex gap-3">
            <Button variant="secondary" onClick={() => { refetchAgents(); refetchStats(); refetchTasks(); refetchCluster(); }}>
              <RefreshCw className="w-4 h-4 mr-2" />
              刷新
            </Button>
            <Button onClick={() => setShowAgentModal(true)}>
              <Plus className="w-4 h-4 mr-2" />
              添加Agent
            </Button>
          </div>
        </div>
      </header>

      <main className="p-6">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 xl:grid-cols-6 gap-4 mb-6">
          <StatCard icon={<Cpu className="w-6 h-6" />} label="总Agent数" value={clusterStats?.total_agents || 0} color="#6366f1" />
          <StatCard icon={<Activity className="w-6 h-6" />} label="活跃Agent" value={clusterStats?.active_agents || 0} color="#10b981" />
          <StatCard icon={<CheckCircle className="w-6 h-6" />} label="完成任务" value={clusterStats?.completed_tasks || 0} color="#10b981" />
          <StatCard icon={<XCircle className="w-6 h-6" />} label="失败任务" value={clusterStats?.failed_tasks || 0} color="#ef4444" />
          <StatCard icon={<Clock className="w-6 h-6" />} label="成功率" value={`${((clusterStats?.success_rate || 0) * 100).toFixed(1)}%`} color="#8b5cf6" />
          <StatCard icon={<AlertCircle className="w-6 h-6" />} label="平均响应" value={`${(clusterStats?.avg_response_time || 0).toFixed(2)}s`} color="#f59e0b" />
        </div>

        <div className="flex gap-2 mb-6 border-b border-slate-700">
          {[
            { key: 'agents', label: 'Agent管理', count: agents.length },
            { key: 'tasks', label: '任务列表', count: tasks.length },
            { key: 'console', label: '任务控制台', count: null },
          ].map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key as any)}
              className={`px-4 py-2 font-medium transition-colors ${
                activeTab === tab.key
                  ? 'text-primary-500 border-b-2 border-primary-500'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              {tab.label}
              {tab.count !== null && ` (${tab.count})`}
            </button>
          ))}
        </div>

        {activeTab === 'agents' && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {agents.map((agent: Agent) => (
              <AgentCard key={agent.id} agent={agent} onDelete={() => deleteAgent.mutate(agent.id)} />
            ))}
            {agents.length === 0 && (
              <div className="col-span-full text-center py-12 text-slate-400">
                暂无Agent，点击"添加Agent"创建一个
              </div>
            )}
          </div>
        )}

        {activeTab === 'tasks' && (
          <Card>
            <CardHeader>
              <CardTitle>任务列表</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-slate-700">
                      <th className="text-left py-3 px-4 text-sm font-medium text-slate-400">描述</th>
                      <th className="text-left py-3 px-4 text-sm font-medium text-slate-400">状态</th>
                      <th className="text-left py-3 px-4 text-sm font-medium text-slate-400">优先级</th>
                      <th className="text-left py-3 px-4 text-sm font-medium text-slate-400">创建时间</th>
                    </tr>
                  </thead>
                  <tbody>
                    {tasks.map((task: Task) => (
                      <tr key={task.id} className="border-b border-slate-700/50">
                        <td className="py-3 px-4 text-sm text-white">{task.description}</td>
                        <td className="py-3 px-4">
                          <Badge variant={taskStatusColors[task.status as keyof typeof taskStatusColors] || 'default'}>
                            {task.status.toUpperCase()}
                          </Badge>
                        </td>
                        <td className="py-3 px-4 text-sm text-slate-400">{task.priority}</td>
                        <td className="py-3 px-4 text-sm text-slate-400">
                          {new Date(task.created_at).toLocaleString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {tasks.length === 0 && (
                  <div className="text-center py-8 text-slate-400">暂无任务</div>
                )}
              </div>
            </CardContent>
          </Card>
        )}

        {activeTab === 'console' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Play className="w-5 h-5 text-primary-500" />
                  单任务执行
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div>
                    <label className="label">任务描述</label>
                    <textarea
                      className="input min-h-[100px] resize-y"
                      placeholder="输入任务描述..."
                      value={taskDescription}
                      onChange={(e) => setTaskDescription(e.target.value)}
                    />
                  </div>
                  <div>
                    <label className="label">优先级: {priority}</label>
                    <input
                      type="range"
                      min="0"
                      max="10"
                      value={priority}
                      onChange={(e) => setPriority(Number(e.target.value))}
                      className="w-full"
                    />
                  </div>
                  <Button onClick={handleCreateTask} disabled={!taskDescription.trim()}>
                    <Play className="w-4 h-4 mr-2" />
                    执行任务
                  </Button>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Layers className="w-5 h-5 text-success-500" />
                  集群协作执行
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div>
                    <label className="label">复杂任务描述</label>
                    <textarea
                      className="input min-h-[100px] resize-y"
                      placeholder="输入需要分解的复杂任务..."
                      value={clusterDescription}
                      onChange={(e) => setClusterDescription(e.target.value)}
                    />
                  </div>
                  <div>
                    <label className="label">Agent数量: {numAgents}</label>
                    <input
                      type="range"
                      min="2"
                      max="5"
                      value={numAgents}
                      onChange={(e) => setNumAgents(Number(e.target.value))}
                      className="w-full"
                    />
                  </div>
                  <Button onClick={handleExecuteCluster} disabled={!clusterDescription.trim()}>
                    <Layers className="w-4 h-4 mr-2" />
                    启动集群协作
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>
        )}
      </main>

      <Modal
        isOpen={showAgentModal}
        onClose={() => setShowAgentModal(false)}
        title="添加新Agent"
        footer={
          <>
            <Button variant="secondary" onClick={() => setShowAgentModal(false)}>取消</Button>
            <Button onClick={handleCreateAgent} disabled={!agentForm.name.trim()}>创建Agent</Button>
          </>
        }
      >
        <div className="space-y-4">
          <Input
            label="Agent名称"
            placeholder="例如：代码助手"
            value={agentForm.name}
            onChange={(e) => setAgentForm({ ...agentForm, name: e.target.value })}
          />
          <div>
            <label className="label">能力标签</label>
            <div className="flex flex-wrap gap-2">
              {capabilities.map((cap) => (
                <button
                  key={cap}
                  onClick={() => {
                    setAgentForm({
                      ...agentForm,
                      capabilities: agentForm.capabilities.includes(cap)
                        ? agentForm.capabilities.filter((c) => c !== cap)
                        : [...agentForm.capabilities, cap],
                    });
                  }}
                  className={`px-3 py-1 text-sm rounded-full border transition-colors ${
                    agentForm.capabilities.includes(cap)
                      ? 'bg-primary-600 border-primary-600 text-white'
                      : 'bg-slate-700 border-slate-600 text-slate-300 hover:border-primary-500'
                  }`}
                >
                  {cap}
                </button>
              ))}
            </div>
          </div>
        </div>
      </Modal>
    </div>
  );
}

function StatCard({ icon, label, value, color }: { icon: React.ReactNode; label: string; value: string | number; color: string }) {
  return (
    <Card>
      <div className="flex items-center gap-3 mb-3" style={{ color }}>
        {icon}
        <span className="text-sm text-slate-400">{label}</span>
      </div>
      <p className="text-2xl font-bold text-white">{value}</p>
    </Card>
  );
}

function AgentCard({ agent, onDelete }: { agent: Agent; onDelete: () => void }) {
  const colors = statusColors[agent.status as keyof typeof statusColors] || statusColors.offline;
  
  return (
    <Card>
      <div className="flex justify-between items-start mb-4">
        <div className="flex items-center gap-3">
          <div className={`p-3 rounded-xl ${colors.bg}`}>
            <Cpu className={`w-6 h-6 ${colors.text}`} />
          </div>
          <div>
            <h3 className="font-semibold text-white">{agent.name}</h3>
            <Badge variant={agent.status === 'idle' ? 'success' : agent.status === 'busy' ? 'warning' : 'default'}>
              {agent.status.toUpperCase()}
            </Badge>
          </div>
        </div>
        <Button variant="ghost" size="icon" onClick={onDelete}>
          <Trash2 className="w-4 h-4 text-slate-400 hover:text-danger-500" />
        </Button>
      </div>
      
      <div className="mb-4">
        <p className="text-xs text-slate-400 mb-2">能力标签</p>
        <div className="flex flex-wrap gap-1">
          {agent.capabilities.map((cap) => (
            <Badge key={cap} variant="default">{cap}</Badge>
          ))}
        </div>
      </div>
      
      <div className="grid grid-cols-2 gap-3 pt-4 border-t border-slate-700">
        <div>
          <p className="text-xs text-slate-400">模型</p>
          <p className="text-sm font-medium text-white">{agent.model}</p>
        </div>
        <div>
          <p className="text-xs text-slate-400">提供商</p>
          <p className="text-sm font-medium text-white">{agent.provider}</p>
        </div>
        <div>
          <p className="text-xs text-slate-400">完成任务</p>
          <p className="text-sm font-medium text-white">{agent.stats.total_tasks}</p>
        </div>
        <div>
          <p className="text-xs text-slate-400">成功率</p>
          <p className="text-sm font-medium text-white">
            {agent.stats.total_tasks > 0
              ? `${((agent.stats.success_count / agent.stats.total_tasks) * 100).toFixed(1)}%`
              : '0%'}
          </p>
        </div>
      </div>
    </Card>
  );
}
