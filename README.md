# Agent Cluster Orchestrator

## 快速开始

### 1. 安装后端依赖

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件，填入你的 API Key
```

### 3. 启动后端服务

```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

后端服务将在 http://localhost:8000 启动

### 4. 启动前端服务

```bash
cd frontend
npm install
npm run dev
```

前端服务将在 http://localhost:3000 启动

### 5. 访问系统

打开浏览器访问 http://localhost:3000

## API 文档

启动后端后，访问 http://localhost:8000/docs 查看完整的 API 文档

## 主要功能

- **Agent管理**: 注册、注销、监控Agent状态
- **任务调度**: 智能任务分发、优先级队列
- **集群协作**: 复杂任务自动分解并行执行
- **实时监控**: WebSocket实时状态更新
- **LLM集成**: 支持OpenAI和Anthropic Claude

## 配置说明

### 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| OPENAI_API_KEY | OpenAI API密钥 | - |
| ANTHROPIC_API_KEY | Anthropic API密钥 | - |
| DEFAULT_MODEL | 默认LLM模型 | gpt-4 |
| DEFAULT_PROVIDER | 默认LLM提供商 | openai |
| MAX_CONCURRENT_TASKS | 最大并发任务数 | 10 |
| TASK_TIMEOUT | 任务超时时间(秒) | 300 |
