# Agent 集群编排系统 - 架构文档

## 快速开始

### 方式一：直接打开 HTML 页面
直接在浏览器中打开 `architecture.html` 文件即可查看。

### 方式二：使用内置服务器
```bash
cd /workspace/docs

# 使用 Python 内置服务器
python3 -m http.server 8080

# 或使用提供的启动脚本
./start.sh
```
然后访问：http://localhost:8080/architecture.html

### 方式三：使用文件监控服务器 (推荐)
```bash
cd /workspace/docs
python3 watch_and_serve.py --port 8080
```
这个服务会自动监控项目文件变化，当文件修改时会自动更新时间戳。

## 文档内容概览

### 📋 系统概览
- 系统组成架构图
- 性能特性
- 安全特性
- 可观测性特性

### 🏗️ 系统架构
- 整体架构设计（分层）
- 目录结构
- 数据流向

### 🧩 核心组件
- 🔐 认证系统（JWT、API Key）
- 🗂️ 缓存策略（多级缓存）
- 📡 WebSocket 连接管理
- 🤖 Agent 生命周期

### 🔄 任务流程
- 单任务执行流程
- 集群任务执行流程

### 📊 时序图
- 完整任务执行时序
- WebSocket 实时通信时序

### 🔌 API 端点
- Agent API
- Task API
- Auth API
- 健康检查 & 监控 API

### 🚀 部署架构
- Kubernetes 部署
- Docker Compose (开发环境)
- 技术栈

## 图表类型

本文档使用 **Mermaid** 绘制所有图表，包括：

- Flowchart（流程图）
- Sequence Diagram（时序图）
- State Diagram（状态图）
- Architecture Diagram（架构图）

## 文件结构

```
/workspace/docs/
├── architecture.html      # 主文档页面
├── watch_and_serve.py     # 文件监控和服务器
├── start.sh               # 快速启动脚本
└── README.md              # 本文件
```

## 自动更新

当你修改项目中的任何源文件时：

1. 如果使用 `watch_and_serve.py`，它会检测到变化并更新文档时间戳
2. 刷新浏览器即可查看最新的架构文档

## 技术栈

- **HTML5** + **Tailwind CSS** - 界面
- **Mermaid.js** - 图表渲染
- **Python 3** - 服务器和文件监控

## 浏览器兼容性

推荐使用现代浏览器：
- Chrome 80+
- Firefox 75+
- Safari 13+
- Edge 80+
