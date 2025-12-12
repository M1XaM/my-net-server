import os
import json
import asyncio
import logging
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Header
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .static_check import ast_static_check
from .container_pool import get_pool, shutdown_pool
from .kafka_consumer import create_kafka_runner, get_kafka_runner

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

STATIC_CHECK = os.environ.get("STATIC_CHECK", "false").lower() == "true"
TIMEOUT = int(os.environ.get("TIMEOUT", "10"))
KAFKA_ENABLED = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "") != ""

# Dashboard WebSocket connections
dashboard_connections: list[WebSocket] = []


async def broadcast_to_dashboard(event: dict):
    """Broadcast an event to all connected dashboard clients."""
    if not dashboard_connections:
        return
    
    message = json.dumps(event)
    disconnected = []
    
    for ws in dashboard_connections:
        try:
            await ws.send_text(message)
        except Exception:
            disconnected.append(ws)
    
    for ws in disconnected:
        if ws in dashboard_connections:
            dashboard_connections.remove(ws)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - initialize pool on startup, cleanup on shutdown."""
    logger.info("Starting up runner service...")
    
    # Initialize the container pool
    try:
        pool = await get_pool()
        # Register dashboard broadcast callback
        pool.add_event_callback(broadcast_to_dashboard)
        logger.info(f"Container pool initialized with {pool.pool_size} workers")
    except Exception as e:
        logger.error(f"Failed to initialize container pool: {e}")
        raise
    
    # Initialize Kafka consumer if enabled
    kafka_runner = None
    if KAFKA_ENABLED:
        try:
            static_checker = ast_static_check if STATIC_CHECK else None
            kafka_runner = create_kafka_runner(get_pool, static_checker, TIMEOUT)
            await kafka_runner.start()
            logger.info("Kafka code runner started successfully")
        except Exception as e:
            logger.warning(f"Failed to start Kafka consumer (HTTP endpoint still available): {e}")
    else:
        logger.info("Kafka not configured, using HTTP-only mode")
    
    yield
    
    # Shutdown Kafka consumer
    if kafka_runner:
        await kafka_runner.stop()
    
    # Shutdown the container pool
    logger.info("Shutting down runner service...")
    await shutdown_pool()


app = FastAPI(lifespan=lifespan)


class CodeRequest(BaseModel):
    code: str
    user_id: Optional[str] = "anonymous"


# Dashboard routes
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    """Serve the dashboard HTML page."""
    static_dir = Path(__file__).parent / "static"
    dashboard_file = static_dir / "dashboard.html"
    
    if dashboard_file.exists():
        return HTMLResponse(content=dashboard_file.read_text())
    else:
        return HTMLResponse(content="<h1>Dashboard not found</h1>", status_code=404)


@app.websocket("/ws/dashboard")
async def websocket_dashboard(websocket: WebSocket):
    """WebSocket endpoint for dashboard real-time updates."""
    await websocket.accept()
    dashboard_connections.append(websocket)
    logger.info(f"Dashboard client connected. Total: {len(dashboard_connections)}")
    
    try:
        # Send initial pool status
        pool = await get_pool()
        health = await pool.health_check()
        await websocket.send_text(json.dumps({
            "type": "pool_status",
            "workers": health["workers"]
        }))
        
        # Send current stats
        stats = pool.get_stats()
        await websocket.send_text(json.dumps({
            "type": "stats",
            "totalExecutions": stats["total_executions"],
            "totalExecTime": stats["total_exec_time_ms"],
            "totalLines": stats["total_lines"],
            "successCount": stats["success_count"],
        }))
        
        # Send execution history
        history = pool.get_execution_history(50)
        await websocket.send_text(json.dumps({
            "type": "history",
            "executions": history
        }))
        
        # Keep connection alive
        while True:
            try:
                # Wait for messages (ping/pong or close)
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                # Echo back or handle commands if needed
            except asyncio.TimeoutError:
                # Send periodic pool status updates
                try:
                    health = await pool.health_check()
                    await websocket.send_text(json.dumps({
                        "type": "pool_status",
                        "workers": health["workers"]
                    }))
                except Exception:
                    break
    
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.warning(f"Dashboard WebSocket error: {e}")
    finally:
        if websocket in dashboard_connections:
            dashboard_connections.remove(websocket)
        logger.info(f"Dashboard client disconnected. Total: {len(dashboard_connections)}")


@app.get("/health")
async def health():
    """Health check endpoint with pool status."""
    try:
        pool = await get_pool()
        pool_health = await pool.health_check()
        return {
            "status": "healthy",
            "pool": pool_health
        }
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "error": str(e)}
        )


@app.post("/run-code")
async def run_code_executor(request_data: CodeRequest):
    """
    Execute Python code safely in an isolated container.
    
    1. Performs static analysis to block dangerous constructs
    2. Sends code to an available worker container from the pool
    3. Returns execution result
    """
    code = request_data.code

    # Static check for forbidden constructs
    if STATIC_CHECK:
        static_issues = ast_static_check(code)
        if static_issues:
            return JSONResponse(
                status_code=403,
                content={
                    'error': 'forbidden constructs found',
                    'details': static_issues
                }
            )

    # Execute in isolated container
    try:
        pool = await get_pool()
        user_id = request_data.user_id or "anonymous"
        result = await pool.execute_code(code, timeout=TIMEOUT, user_id=user_id)
        
        if "error" in result:
            status_code = result.get("status_code", 500)
            if status_code == 408:
                raise HTTPException(status_code=408, detail="execution timed out")
            elif status_code == 503:
                raise HTTPException(status_code=503, detail="no available workers")
            else:
                raise HTTPException(status_code=status_code, detail=result["error"])
        
        return {
            'stdout': result.get('stdout', ''),
            'stderr': result.get('stderr', ''),
            'return_code': result.get('return_code', 0),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing code: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/dashboard/stats")
async def dashboard_stats():
    """Get execution statistics for the dashboard."""
    pool = await get_pool()
    return pool.get_stats()


@app.get("/dashboard/history")
async def dashboard_history(limit: int = 50):
    """Get recent execution history."""
    pool = await get_pool()
    return pool.get_execution_history(limit)