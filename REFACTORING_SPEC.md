# Agent Cluster Orchestrator - 重构规范文档

## 一、重构原则

### 1.1 命名规范
- **文件命名**: 至少4个单词，见名知意
- **命名格式**: 小写下划线分隔 (snake_case)
- **模块命名**: 小写下划线分隔
- **类命名**: 大驼峰 (PascalCase)
- **常量命名**: 全大写下划线分隔

### 1.2 模块化原则
- **单一职责**: 每个文件只负责一件事
- **高内聚低耦合**: 相关功能放在一起
- **分层清晰**: API → Service → Repository → Model

## 二、后端文件命名规范

### 2.1 配置文件
| 原命名 | 新命名 | 说明 |
|--------|--------|------|
| `config.py` | `application_configuration.py` | 应用配置 |
| `database.py` | `database_connection_manager.py` | 数据库连接管理 |
| `logging.py` | `structured_logging_config.py` | 日志配置 |
| `exceptions.py` | `custom_exceptions_handler.py` | 异常处理 |

### 2.2 API层
| 原命名 | 新命名 | 说明 |
|--------|--------|------|
| `agents.py` | `agent_management_endpoints.py` | Agent管理端点 |
| `tasks.py` | `task_execution_endpoints.py` | 任务执行端点 |
| `cluster.py` | `cluster_orchestration_endpoints.py` | 集群编排端点 |
| `health.py` | `health_check_endpoints.py` | 健康检查端点 |

### 2.3 服务层
| 原命名 | 新命名 | 说明 |
|--------|--------|------|
| `agent_service.py` | `agent_lifecycle_management_service.py` | Agent生命周期管理 |
| `task_service.py` | `task_dispatch_and_execution_service.py` | 任务调度执行服务 |

### 2.4 仓储层
| 原命名 | 新命名 | 说明 |
|--------|--------|------|
| `agent_repo.py` | `agent_persistence_repository.py` | Agent持久化仓储 |
| `task_repo.py` | `task_persistence_repository.py` | 任务持久化仓储 |

### 2.5 LLM层
| 原命名 | 新命名 | 说明 |
|--------|--------|------|
| `base.py` | `base_llm_provider_interface.py` | LLM基础接口 |
| `openai_provider.py` | `openai_llm_provider.py` | OpenAI实现 |
| `anthropic_provider.py` | `anthropic_llm_provider.py` | Anthropic实现 |
| `manager.py` | `llm_provider_manager.py` | LLM管理器 |

### 2.6 数据模型
| 原命名 | 新命名 | 说明 |
|--------|--------|------|
| `agent.py` | `agent_data_model.py` | Agent数据模型 |
| `task.py` | `task_data_model.py` | 任务数据模型 |

### 2.7 Schema
| 原命名 | 新命名 | 说明 |
|--------|--------|------|
| `agent.py` | `agent_api_schemas.py` | Agent API Schema |
| `task.py` | `task_api_schemas.py` | 任务API Schema |

## 三、前端文件命名规范

### 3.1 API客户端
| 原命名 | 新命名 | 说明 |
|--------|--------|------|
| `api/index.ts` | `api/http_client_configuration.ts` | HTTP客户端配置 |
| `hooks/useApi.ts` | `hooks/use_agent_cluster_hooks.ts` | API Hooks |

### 3.2 组件
| 原命名 | 新命名 | 说明 |
|--------|--------|------|
| `Dashboard.tsx` | `cluster_dashboard_view.tsx` | 集群仪表盘 |
| `AgentForm.tsx` | `create_agent_form_modal.tsx` | 创建Agent表单 |
| `TaskConsole.tsx` | `task_execution_console.tsx` | 任务控制台 |
| `Button.tsx` | `ui_button_component.tsx` | 按钮组件 |
| `Input.tsx` | `ui_input_component.tsx` | 输入框组件 |
| `Modal.tsx` | `ui_modal_dialog_component.tsx` | 模态框组件 |
| `Card.tsx` | `ui_card_container_component.tsx` | 卡片组件 |
| `Badge.tsx` | `ui_status_badge_component.tsx` | 状态徽章组件 |

### 3.3 状态管理
| 原命名 | 新命名 | 说明 |
|--------|--------|------|
| `appStore.ts` | `app_global_state_store.ts` | 全局状态存储 |

### 3.4 类型定义
| 原命名 | 新命名 | 说明 |
|--------|--------|------|
| `types/index.ts` | `types/application_type_definitions.ts` | 类型定义 |

## 四、目录结构

### 4.1 后端结构
```
backend/
├── app/
│   ├── __init__.py
│   ├── application_configuration.py      # 应用配置
│   ├── database_connection_manager.py     # 数据库管理
│   ├── main_fastapi_application.py      # FastAPI入口
│   ├── api/
│   │   ├── __init__.py
│   │   ├── health_check_endpoints.py     # 健康检查
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── agent_management_endpoints.py
│   │       ├── task_execution_endpoints.py
│   │       └── cluster_orchestration_endpoints.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── structured_logging_config.py
│   │   └── custom_exceptions_handler.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── agent_data_model.py
│   │   └── task_data_model.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── agent_api_schemas.py
│   │   └── task_api_schemas.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── agent_lifecycle_management_service.py
│   │   └── task_dispatch_and_execution_service.py
│   ├── repositories/
│   │   ├── __init__.py
│   │   ├── agent_persistence_repository.py
│   │   └── task_persistence_repository.py
│   └── llm/
│       ├── __init__.py
│       ├── base_llm_provider_interface.py
│       ├── openai_llm_provider.py
│       ├── anthropic_llm_provider.py
│       └── llm_provider_manager.py
├── tests/
│   ├── conftest.py
│   ├── unit/
│   │   ├── test_agent_service.py
│   │   └── test_task_service.py
│   └── integration/
│       ├── test_agent_api.py
│       └── test_task_api.py
├── Dockerfile
└── requirements.txt
```

### 4.2 前端结构
```
frontend/
├── src/
│   ├── main_application_entry.tsx
│   ├── index.css
│   ├── api/
│   │   └── http_client_configuration.ts
│   ├── components/
│   │   ├── dashboard/
│   │   │   ├── cluster_dashboard_view.tsx
│   │   │   └── __init__.py
│   │   ├── agents/
│   │   │   ├── create_agent_form_modal.tsx
│   │   │   └── __init__.py
│   │   ├── tasks/
│   │   │   ├── task_execution_console.tsx
│   │   │   └── __init__.py
│   │   └── ui/
│   │       ├── ui_button_component.tsx
│   │       ├── ui_input_component.tsx
│   │       ├── ui_modal_dialog_component.tsx
│   │       ├── ui_card_container_component.tsx
│   │       ├── ui_status_badge_component.tsx
│   │       └── __init__.py
│   ├── hooks/
│   │   └── use_agent_cluster_hooks.ts
│   ├── stores/
│   │   └── app_global_state_store.ts
│   └── types/
│       └── application_type_definitions.ts
├── playwright/
├── Dockerfile
├── package.json
└── vite.config.ts
```

## 五、实施计划

### Phase 1: 后端重构
1. 重命名配置文件
2. 重命名API层文件
3. 重命名服务层文件
4. 重命名仓储层文件
5. 重命名LLM层文件
6. 更新所有导入路径

### Phase 2: 前端重构
1. 重命名API客户端
2. 重命名组件文件
3. 重命名状态管理
4. 更新导入路径

### Phase 3: 测试验证
1. 运行单元测试
2. 运行集成测试
3. 启动应用验证

## 六、注意事项

1. **保持向后兼容**: 重命名时确保API接口不变
2. **分步提交**: 每完成一个模块的重命名就提交
3. **测试先行**: 重构前确保有足够的测试覆盖
4. **文档更新**: 重构完成后更新相关文档
