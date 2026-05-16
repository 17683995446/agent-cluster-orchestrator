import { useState } from 'react';
import { Modal } from '../ui/ui_modal_dialog_component';
import { Button } from '../ui/ui_button_component';

interface CreateAgentFormModalProps {
  onSubmit: (data: {
    name: string;
    capabilities: string[];
    model: string;
    provider: string;
  }) => void;
  onClose: () => void;
}

const CAPABILITY_OPTIONS = [
  'code_generation',
  'code_review',
  'data_analysis',
  'writing',
  'translation',
  'summarization',
  'problem_solving',
  'reasoning',
];

const MODEL_OPTIONS = [
  { label: 'GPT-4', value: 'gpt-4' },
  { label: 'GPT-3.5 Turbo', value: 'gpt-3.5-turbo' },
  { label: 'Claude 3 Opus', value: 'claude-3-opus-20240229' },
  { label: 'Claude 3 Sonnet', value: 'claude-3-sonnet-20240229' },
];

const PROVIDER_OPTIONS = [
  { label: 'OpenAI', value: 'openai' },
  { label: 'Anthropic', value: 'anthropic' },
  { label: 'Local LLM', value: 'local' },
];

export function CreateAgentFormModal({ onSubmit, onClose }: CreateAgentFormModalProps) {
  const [name, setName] = useState('');
  const [capabilities, setCapabilities] = useState<string[]>([]);
  const [model, setModel] = useState('gpt-4');
  const [provider, setProvider] = useState('openai');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;

    onSubmit({
      name: name.trim(),
      capabilities,
      model,
      provider,
    });
  };

  const toggleCapability = (cap: string) => {
    setCapabilities((prev) =>
      prev.includes(cap)
        ? prev.filter((c) => c !== cap)
        : [...prev, cap]
    );
  };

  return (
    <Modal
      isOpen={true}
      onClose={onClose}
      title="Create New Agent"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={!name.trim()}>
            Create Agent
          </Button>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="label">Agent Name</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g., Code Assistant"
            className="input"
          />
        </div>

        <div>
          <label className="label">Capabilities</label>
          <div className="flex flex-wrap gap-2">
            {CAPABILITY_OPTIONS.map((cap) => (
              <button
                key={cap}
                type="button"
                onClick={() => toggleCapability(cap)}
                className={`px-3 py-1 text-sm rounded-full border transition-colors ${
                  capabilities.includes(cap)
                    ? 'bg-primary-600 border-primary-600 text-white'
                    : 'bg-slate-700 border-slate-600 text-slate-300 hover:border-primary-500'
                }`}
              >
                {cap}
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className="label">LLM Model</label>
          <div className="flex gap-2">
            {MODEL_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => setModel(opt.value)}
                className={`flex-1 px-3 py-2 text-sm rounded-lg border transition-colors ${
                  model === opt.value
                    ? 'bg-primary-600 border-primary-600 text-white'
                    : 'bg-slate-700 border-slate-600 text-slate-300'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className="label">LLM Provider</label>
          <div className="flex gap-2">
            {PROVIDER_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => setProvider(opt.value)}
                className={`flex-1 px-3 py-2 text-sm rounded-lg border transition-colors ${
                  provider === opt.value
                    ? 'bg-primary-600 border-primary-600 text-white'
                    : 'bg-slate-700 border-slate-600 text-slate-300'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>
      </form>
    </Modal>
  );
}
