import json
import uuid
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from app.core.security import get_current_user, verify_username_match
from app.db.redis import redis
from app.models.workflow import (
    NodesInput,
    TestConditionNode,
    TestFunctionCode,
    Workflow,
    WorkflowCreate,
    WorkflowRenameInput,
)
from app.utils.timezone import beijing_time_now
from app.workflow.workflow_engine import WorkflowEngine
from app.models.user import User
from app.db.mongo import MongoDB, get_mongo
from app.utils.kafka_producer import kafka_producer_manager

router = APIRouter()


@router.post("/execute")
async def execute_workflow(
    workflow: Workflow,
    current_user: User = Depends(get_current_user),
):
    await verify_username_match(current_user, workflow.username)
    try:
        # 使用异步上下文管理器
        async with WorkflowEngine(
            nodes=workflow.nodes,
            edges=workflow.edges,
            global_variables=workflow.global_variables,
            start_node=workflow.start_node,
        ) as engine:
            # 验证工作流结构
            if not engine.graph[0]:
                return {"code": -1, "msg": engine.graph[-1]}
    except ValueError as e:
        return {"code": -2, "msg": str(e)}
    except Exception as e:
        return {"code": -3, "msg": f"System Error: {str(e)}"}

    # 初始化Redis状态
    redis_conn = await redis.get_task_connection()

    if workflow.resume_task_id:
        task_id = workflow.resume_task_id
        # 1. 合并更新全局变量
        state_key = f"workflow:{task_id}:state"
        state = await redis_conn.get(state_key)
        if not state:
            raise {"code": -2, "msg": str("任务过期，请重新执行！")}

        state_data = json.loads(state)

        # 更新全局变量（深合并）
        def deep_update(target, source):
            for k, v in source.items():
                if isinstance(v, dict) and k in target:
                    deep_update(target[k], v)
                else:
                    target[k] = v

        deep_update(state_data["global_variables"], workflow.global_variables)

        # 保存更新后的状态
        await redis_conn.setex(state_key, 3600, json.dumps(state_data))
    else:
        task_id = str(uuid.uuid4())

    # 存储任务元数据
    await redis_conn.hset(
        name=f"workflow:{task_id}",
        mapping={
            "status": "pending",
            "username": current_user.username,
            "start_time": str(beijing_time_now()),
            "result": "",
            "error": "",
        },
    )

    # 存储节点状态
    node_mapping = {node["id"]: "0" for node in workflow.nodes}
    await redis_conn.hset(name=f"workflow:{task_id}:nodes", mapping=node_mapping)

    # 创建独立的事件流（Stream类型）
    await redis_conn.xadd(
        f"workflow:events:{task_id}",  # 使用新的事件流键
        {
            "type": "workflow",
            "status": "initializing",
            "result": "",
            "error": "",
            "create_time": str(beijing_time_now()),
        },
    )

    pipeline = redis_conn.pipeline()
    pipeline.expire(f"workflow:{task_id}", 3600)
    pipeline.expire(f"workflow:{task_id}:nodes", 3600)
    pipeline.expire(f"workflow:events:{task_id}", 3600)  # 新增事件流过期设置
    await pipeline.execute()

    # 发送到Kafka
    await kafka_producer_manager.send_workflow_task(
        task_id=task_id,
        workflow_data=workflow.model_dump(),
        username=current_user.username,
        resume=True if workflow.resume_task_id else False,
    )

    return {"code": 0, "task_id": task_id, "msg": "Task queued"}


# 测试python代码
@router.post("/test_code", response_model=dict)
async def execute_workflow(
    function_node: TestFunctionCode,
    current_user: User = Depends(get_current_user),
):
    await verify_username_match(current_user, function_node.username)
    test_workflow = {
        "global_variables": function_node.global_variables,
        "nodes": [
            {
                "id": "node_start",
                "type": "start",
                "data": {"name": "Start"},
            },
            {
                "id": function_node.node_id,
                "type": "code",
                "data": {
                    "name": function_node.name,
                    "code": function_node.code,
                    "pip": function_node.pip,
                    "imageUrl": function_node.image_url,
                },
            },
        ],
        "edges": [
            {"source": "node_start", "target": function_node.node_id},
        ],
    }

    try:
        # 使用异步上下文管理器
        async with WorkflowEngine(
            nodes=test_workflow["nodes"],
            edges=test_workflow["edges"],
            global_variables=test_workflow["global_variables"],
        ) as engine:

            # 验证工作流结构
            if not engine.graph[0]:
                return {"code": -1, "result": "", "msg": engine.graph[-1]}

            # 执行工作流
            await engine.start()
            return {"code": 0, "result": engine.context, "msg": ""}

    except ValueError as e:
        return {"code": -2, "result": "", "msg": str(e)}
    # except Exception as e:
    #     return {"code": -3, "result": "", "msg": f"System Error: {str(e)}"}


# 测试条件节点
@router.post("/test_condition", response_model=dict)
async def execute_workflow(
    condition_node: TestConditionNode,
    current_user: User = Depends(get_current_user),
):
    await verify_username_match(current_user, condition_node.username)
    test_workflow = {
        "global_variables": condition_node.global_variables,
        "nodes": [
            {
                "id": "node_start",
                "type": "start",
                "data": {"name": "start"},
            },
            {
                "id": condition_node.node_id,
                "type": "condition",
                "data": {
                    "name": condition_node.name,
                    "conditions": condition_node.conditions,
                },
            },
        ],
        "edges": [
            {"source": "node_start", "target": condition_node.node_id},
        ],
    }

    try:
        # 使用异步上下文管理器
        async with WorkflowEngine(
            nodes=test_workflow["nodes"],
            edges=test_workflow["edges"],
            global_variables=test_workflow["global_variables"],
        ) as engine:

            # 验证工作流结构
            if not engine.graph[0]:
                return {"code": -1, "result": "", "msg": engine.graph[-1]}

            # 执行工作流
            await engine.start()
            return {"code": 0, "result": engine.context, "msg": ""}

    except ValueError as e:
        return {"code": -2, "result": "", "msg": str(e)}
    except Exception as e:
        return {"code": -3, "result": "", "msg": f"System Error: {str(e)}"}


# 创建或修改workflow
@router.post("/workflows", response_model=dict)
async def create_workflow(
    workflow: WorkflowCreate,
    db: MongoDB = Depends(get_mongo),
    current_user: User = Depends(get_current_user),
):
    await verify_username_match(current_user, workflow.username)
    if workflow.workflow_id == "":
        workflow_id = workflow.username + "_" + str(uuid.uuid4())  # 生成 UUIDv4,
    else:
        workflow_id = workflow.workflow_id
    await db.update_workflow(
        workflow_id=workflow_id,
        username=workflow.username,
        workflow_name=workflow.workflow_name,
        workflow_config=workflow.workflow_config,
        start_node=workflow.start_node,
        global_variables=workflow.global_variables,
        nodes=workflow.nodes,
        edges=workflow.edges,
    )
    return {"status": "success"}


# 修改会话名称
@router.post("/workflows/rename", response_model=dict)
async def re_name(
    renameInput: WorkflowRenameInput,
    db: MongoDB = Depends(get_mongo),
    current_user: User = Depends(get_current_user),
):
    await verify_username_match(current_user, renameInput.workflow_id.split("_")[0])

    result = await db.update_workflow_name(
        renameInput.workflow_id, renameInput.workflow_new_name
    )
    if result["status"] == "failed":
        raise HTTPException(status_code=404, detail="Workflow not found")
    return result


# 获取指定 workflow_id 的完整会话记录
@router.get("/workflows/{workflow_id}", response_model=dict)
async def get_workflow(
    workflow_id: str,
    db: MongoDB = Depends(get_mongo),
    current_user: User = Depends(get_current_user),
):
    await verify_username_match(current_user, workflow_id.split("_")[0])
    workflow = await db.get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    user_files = []
    for node in workflow["nodes"]:
        if temp_db := node["data"].get("temp_db"):
            user_files.append(await db.get_files_by_knowledge_base_id(temp_db))

    return {
        "workflow_id": workflow["workflow_id"],
        "workflow_name": workflow["workflow_name"],
        "workflow_config": workflow["workflow_config"],
        "username": workflow["username"],
        "nodes": workflow["nodes"],
        "edges": workflow["edges"],
        "start_node": workflow["start_node"],
        "global_variables": workflow["global_variables"],
        "created_at": workflow["created_at"].isoformat(),
        "last_modify_at": workflow["last_modify_at"].isoformat(),
    }


# 查询指定用户的所有会话
@router.get("/users/{username}/workflows", response_model=list)
async def get_workflows_by_user(
    username: str,
    db: MongoDB = Depends(get_mongo),
    current_user: User = Depends(get_current_user),
):
    await verify_username_match(current_user, username)
    workflows = await db.get_workflows_by_user(username)
    if not workflows:
        return []
    return [
        {
            "workflow_id": workflow["workflow_id"],
            "workflow_name": workflow["workflow_name"],
            "workflow_config": workflow["workflow_config"],
            "created_at": workflow["created_at"].isoformat(),
            "last_modify_at": workflow["last_modify_at"].isoformat(),
        }
        for workflow in workflows
    ]


# 删除指定会话
@router.delete("/workflows/{workflow_id}", response_model=dict)
async def delete_workflow(
    workflow_id: str,
    db: MongoDB = Depends(get_mongo),
    current_user: User = Depends(get_current_user),
):
    await verify_username_match(current_user, workflow_id.split("_")[0])
    result = await db.delete_workflow(workflow_id)
    if result["status"] == "failed":
        raise HTTPException(status_code=404, detail=result["message"])
    return result


# 保存自定义节点
@router.post("/nodes/{username}", response_model=dict)
async def delete_workflow(
    username: str,
    custom_node: NodesInput,
    db: MongoDB = Depends(get_mongo),
    current_user: User = Depends(get_current_user),
):
    await verify_username_match(current_user, username)
    result = await db.update_custom_nodes(
        username, custom_node.custom_node_name, custom_node.custom_node
    )
    if result["status"] == "failed":
        raise HTTPException(status_code=404, detail=result["message"])
    return result


@router.get("/nodes/{username}", response_model=dict)
async def delete_workflow(
    username: str,
    db: MongoDB = Depends(get_mongo),
    current_user: User = Depends(get_current_user),
):
    await verify_username_match(current_user, username)
    result = await db.get_custom_nodes(username)
    return result

# 删除自定义节点
@router.delete("/nodes/{username}/{custom_node_name}", response_model=dict)
async def delete_nodes(
    username: str,
    custom_node_name: str,
    db: MongoDB = Depends(get_mongo),
    current_user: User = Depends(get_current_user),
):
    await verify_username_match(current_user, username)
    result = await db.delete_custom_nodes(username, custom_node_name)
    if result["status"] == "failed":
        raise HTTPException(status_code=404, detail=result["message"])
    return result
