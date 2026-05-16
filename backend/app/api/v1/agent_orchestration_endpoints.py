"""
Agent编排与任务链系统API端点
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from app.services.agent_orchestrator import (
    AgentOrchestrator,
    ChainBuilder,
    ExecutionEngine,
    TaskChain,
    TaskNode,
    WorkflowSystem,
    get_orchestrator,
    get_workflow_system
)
from app.schemas.agent_api_schemas import AgentResponse

router = APIRouter(prefix="/orchestration", tags=["orchestration"])


# ============== 请求/响应模型 ==============

class AgentRegistrationRequest(BaseModel):
    agent_id: str
    capabilities: List[str]
    model_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class AgentRegistrationResponse(BaseModel):
    success: bool
    message: str
    agent_id: str


class OrchestrationRequest(BaseModel):
    task_description: str
    context: Optional[Dict[str, Any]] = None
    agent_ids: Optional[List[str]] = None


class OrchestrationResponse(BaseModel):
    execution_id: str
    status: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class ChainDefinitionRequest(BaseModel):
    name: str
    description: Optional[str] = None
    nodes: Optional[List[Dict[str, Any]]] = None
    entry_node: Optional[str] = None


class ChainExecutionRequest(BaseModel):
    chain_id: str
    initial_context: Dict[str, Any]


class ChainExecutionResponse(BaseModel):
    execution_id: str
    status: str
    result: Optional[Dict[str, Any]] = None


class WorkflowScheduleRequest(BaseModel):
    chain_id: str
    cron_expression: str
    context: Optional[Dict[str, Any]] = None


class WorkflowScheduleResponse(BaseModel):
    workflow_id: str
    success: bool


class SystemStatusResponse(BaseModel):
    registered_agents: int
    saved_chains: int
    scheduled_workflows: int


# ============== API端点 ==============

@router.post("/agents/register", response_model=AgentRegistrationResponse)
async def register_agent(
    request: AgentRegistrationRequest,
    orchestrator: AgentOrchestrator = Depends(get_orchestrator)
):
    """
    注册Agent到编排系统
    """
    try:
        orchestrator.register_agent(
            agent_id=request.agent_id,
            capabilities=request.capabilities,
            model_id=request.model_id,
            metadata=request.metadata
        )
        
        return AgentRegistrationResponse(
            success=True,
            message="Agent registered successfully",
            agent_id=request.agent_id
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/orchestrate", response_model=OrchestrationResponse)
async def orchestrate_task(
    request: OrchestrationRequest,
    orchestrator: AgentOrchestrator = Depends(get_orchestrator)
):
    """
    智能编排任务
    
    系统会自动分析任务、选择Agent并执行
    """
    execution_id = str(uuid4())
    
    try:
        result = await orchestrator.orchestrate(
            task_description=request.task_description,
            context=request.context
        )
        
        return OrchestrationResponse(
            execution_id=execution_id,
            status=result.get("status", "completed"),
            result=result
        )
        
    except Exception as e:
        return OrchestrationResponse(
            execution_id=execution_id,
            status="failed",
            error=str(e)
        )


@router.post("/chains", response_model=ChainExecutionResponse)
async def create_and_execute_chain(
    request: ChainExecutionRequest,
    orchestrator: AgentOrchestrator = Depends(get_orchestrator),
    workflow_system: WorkflowSystem = Depends(get_workflow_system)
):
    """
    执行已保存的任务链
    """
    try:
        chain = workflow_system.get_chain(request.chain_id)
        if not chain:
            raise HTTPException(status_code=404, detail="Chain not found")
        
        result = await orchestrator.engine.execute_chain(
            chain,
            request.initial_context
        )
        
        return ChainExecutionResponse(
            execution_id=str(uuid4()),
            status="completed",
            result=result
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chains/builder", response_model=Dict[str, Any])
async def build_simple_chain(
    name: str,
    agent_id: str,
    input_template: str,
    model_id: Optional[str] = None,
    workflow_system: WorkflowSystem = Depends(get_workflow_system)
):
    """
    快速构建并保存一个简单的Agent任务链
    """
    builder = ChainBuilder(name)
    builder.agent_node(
        agent_id=agent_id,
        model_id=model_id,
        input_template=input_template
    )
    
    chain = builder.build()
    chain_id = workflow_system.save_chain(chain)
    
    return {
        "chain_id": chain_id,
        "success": True,
        "message": "Chain created successfully"
    }


@router.post("/workflows/schedule", response_model=WorkflowScheduleResponse)
async def schedule_workflow(
    request: WorkflowScheduleRequest,
    workflow_system: WorkflowSystem = Depends(get_workflow_system)
):
    """
    调度一个工作流
    """
    try:
        workflow_id = await workflow_system.schedule_workflow(
            chain_id=request.chain_id,
            cron_expression=request.cron_expression,
            context=request.context
        )
        
        return WorkflowScheduleResponse(
            workflow_id=workflow_id,
            success=True
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/workflows/{workflow_id}/run", response_model=OrchestrationResponse)
async def run_scheduled_workflow(
    workflow_id: str,
    context_override: Optional[Dict[str, Any]] = None,
    workflow_system: WorkflowSystem = Depends(get_workflow_system)
):
    """
    立即运行一个已调度的工作流
    """
    try:
        result = await workflow_system.run_workflow(
            workflow_id,
            context_override
        )
        
        return OrchestrationResponse(
            execution_id=str(uuid4()),
            status="completed",
            result=result
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status", response_model=SystemStatusResponse)
async def get_system_status(
    orchestrator: AgentOrchestrator = Depends(get_orchestrator),
    workflow_system: WorkflowSystem = Depends(get_workflow_system)
):
    """
    获取编排系统状态
    """
    return SystemStatusResponse(
        registered_agents=len(orchestrator._registered_agents),
        saved_chains=len(workflow_system._saved_chains),
        scheduled_workflows=len(workflow_system._scheduled_workflows)
    )


@router.websocket("/ws/execution/{execution_id}")
async def websocket_execution_monitor(
    websocket: WebSocket,
    execution_id: str
):
    """
    WebSocket端点 - 实时监控任务链执行
    """
    await websocket.accept()
    
    try:
        # 这里可以实现执行进度的实时推送
        while True:
            await asyncio.sleep(1)
            await websocket.send_json({
                "execution_id": execution_id,
                "status": "monitoring",
                "timestamp": datetime.utcnow().isoformat()
            })
            
    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({
                "error": str(e)
            })
        except:
            pass


@router.get("/agents/list")
async def list_registered_agents(
    orchestrator: AgentOrchestrator = Depends(get_orchestrator)
) -> Dict[str, Any]:
    """
    列出所有已注册的Agent
    """
    return {
        "agents": list(orchestrator._registered_agents.values())
    }
