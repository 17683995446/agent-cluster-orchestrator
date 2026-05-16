import { useState } from 'react';
import { Play, Layers } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardContent } from '../ui/ui_card_container_component';
import { Button } from '../ui/ui_button_component';

interface TaskExecutionConsoleProps {
  onCreateTask: (description: string, priority: number) => void;
  onExecuteClusterTask: (description: string, numAgents: number) => void;
}

const SAMPLE_TASKS = [
  'Write a Python quicksort algorithm',
  'Analyze this data trend and give suggestions',
  'Translate this English paragraph to Chinese',
  'Write a business email',
];

export function TaskExecutionConsole({
  onCreateTask,
  onExecuteClusterTask,
}: TaskExecutionConsoleProps) {
  const [taskDescription, setTaskDescription] = useState('');
  const [priority, setPriority] = useState(0);
  const [clusterDescription, setClusterDescription] = useState('');
  const [numAgents, setNumAgents] = useState(3);

  const handleSubmitTask = (e: React.FormEvent) => {
    e.preventDefault();
    if (!taskDescription.trim()) return;
    onCreateTask(taskDescription.trim(), priority);
    setTaskDescription('');
    setPriority(0);
  };

  const handleSubmitClusterTask = (e: React.FormEvent) => {
    e.preventDefault();
    if (!clusterDescription.trim()) return;
    onExecuteClusterTask(clusterDescription.trim(), numAgents);
    setClusterDescription('');
  };

  const handleUseSample = (sample: string) => {
    setTaskDescription(sample);
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Play className="w-5 h-5 text-primary-500" />
            Single Task Execution
          </CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmitTask} className="space-y-4">
            <div>
              <label className="label">Task Description</label>
              <textarea
                className="input min-h-[100px] resize-y"
                placeholder="Enter task description..."
                value={taskDescription}
                onChange={(e) => setTaskDescription(e.target.value)}
              />
            </div>

            <div>
              <label className="label">Priority: {priority}</label>
              <input
                type="range"
                min="0"
                max="10"
                value={priority}
                onChange={(e) => setPriority(Number(e.target.value))}
                className="w-full"
              />
            </div>

            <div>
              <p className="text-xs text-slate-400 mb-2">Sample Tasks:</p>
              <div className="flex flex-wrap gap-2">
                {SAMPLE_TASKS.map((sample, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => handleUseSample(sample)}
                    className="text-xs px-2 py-1 bg-slate-700 text-slate-400 rounded border border-slate-600 hover:border-primary-500 transition-colors"
                  >
                    {sample.substring(0, 20)}...
                  </button>
                ))}
              </div>
            </div>

            <Button type="submit" disabled={!taskDescription.trim()} className="w-full">
              <Play className="w-4 h-4 mr-2" />
              Execute Task
            </Button>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Layers className="w-5 h-5 text-success-500" />
            Cluster Collaboration
          </CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmitClusterTask} className="space-y-4">
            <div>
              <label className="label">Complex Task Description</label>
              <textarea
                className="input min-h-[100px] resize-y"
                placeholder="Enter complex task to decompose..."
                value={clusterDescription}
                onChange={(e) => setClusterDescription(e.target.value)}
              />
            </div>

            <div>
              <label className="label">Number of Agents: {numAgents}</label>
              <input
                type="range"
                min="2"
                max="5"
                value={numAgents}
                onChange={(e) => setNumAgents(Number(e.target.value))}
                className="w-full"
              />
            </div>

            <Button
              type="submit"
              disabled={!clusterDescription.trim()}
              className="w-full"
              variant="secondary"
            >
              <Layers className="w-4 h-4 mr-2" />
              Start Cluster Collaboration
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
