"""
Container Pool Manager - manages a pool of isolated worker containers.
Uses Docker SDK to create, manage, and communicate with worker containers.
"""
import asyncio
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional, Callable, Any
import httpx
import docker
from docker.models.containers import Container

logger = logging.getLogger(__name__)


@dataclass
class ExecutionInfo:
    """Information about a code execution."""
    execution_id: str
    user_id: str
    code: str
    worker_name: str
    start_time: float
    end_time: Optional[float] = None
    duration_ms: Optional[int] = None
    success: bool = False
    return_code: Optional[int] = None


@dataclass
class WorkerContainer:
    """Represents a worker container in the pool."""
    container: Container
    port: int
    container_ip: str = ""
    busy: bool = False
    last_used: float = 0.0
    current_execution: Optional[ExecutionInfo] = None
    exec_start_time: Optional[float] = None
    
    @property
    def url(self) -> str:
        # Use container IP on internal network
        return f"http://{self.container_ip}:8000"
    
    @property
    def name(self) -> str:
        return self.container.name


class ContainerPool:
    """
    Manages a pool of worker containers for code execution.
    
    Features:
    - Pre-spawns a configurable number of containers at startup
    - Acquires/releases containers for request handling
    - Health checks and automatic recovery
    - Graceful shutdown
    - Execution tracking for dashboard
    """
    
    WORKER_NETWORK_NAME = "runner-worker-net"
    
    def __init__(
        self,
        pool_size: int = 5,
        base_port: int = 9000,
        worker_image: str = "runner-worker:latest",
        network_name: Optional[str] = None,
        container_memory_limit: str = "128m",
        container_cpu_limit: float = 0.25,
    ):
        self.pool_size = pool_size
        self.base_port = base_port
        self.worker_image = worker_image
        self.network_name = network_name
        self.container_memory_limit = container_memory_limit
        self.container_cpu_limit = container_cpu_limit
        
        self.workers: list[WorkerContainer] = []
        self._lock = asyncio.Lock()
        self._client: Optional[docker.DockerClient] = None
        self._initialized = False
        self._http_client: Optional[httpx.AsyncClient] = None
        self._worker_network = None
        
        # Dashboard/tracking support
        self._event_callbacks: list[Callable[[dict], Any]] = []
        self._execution_history: list[ExecutionInfo] = []
        self._max_history = 100
        
        # Statistics
        self.stats = {
            "total_executions": 0,
            "total_exec_time_ms": 0,
            "total_lines": 0,
            "success_count": 0,
        }
    
    def add_event_callback(self, callback: Callable[[dict], Any]) -> None:
        """Add a callback to be notified of pool events."""
        self._event_callbacks.append(callback)
    
    def remove_event_callback(self, callback: Callable[[dict], Any]) -> None:
        """Remove an event callback."""
        if callback in self._event_callbacks:
            self._event_callbacks.remove(callback)
    
    async def _emit_event(self, event: dict) -> None:
        """Emit an event to all registered callbacks."""
        for callback in self._event_callbacks:
            try:
                result = callback(event)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.warning(f"Error in event callback: {e}")
    
    async def initialize(self) -> None:
        """Initialize the container pool by building image and spawning workers."""
        if self._initialized:
            return
        
        logger.info("Initializing container pool...")
        
        # Initialize Docker client
        self._client = docker.from_env()
        self._http_client = httpx.AsyncClient(timeout=30.0)
        
        # Create internal network for worker communication
        await self._create_worker_network()
        
        # Connect this container (runner) to the worker network
        await self._connect_self_to_worker_network()
        
        # Build the worker image
        await self._build_worker_image()
        
        # Clean up any existing worker containers from previous runs
        await self._cleanup_old_workers()
        
        # Spawn worker containers
        await self._spawn_workers()
        
        self._initialized = True
        logger.info(f"Container pool initialized with {len(self.workers)} workers")
    
    async def _create_worker_network(self) -> None:
        """Create an internal Docker network for worker containers."""
        logger.info("Creating worker network...")
        
        loop = asyncio.get_event_loop()
        
        # Check if network already exists
        try:
            networks = await loop.run_in_executor(
                None,
                lambda: self._client.networks.list(names=[self.WORKER_NETWORK_NAME])
            )
            if networks:
                self._worker_network = networks[0]
                logger.info(f"Using existing network: {self.WORKER_NETWORK_NAME}")
        except Exception as e:
            logger.warning(f"Error checking for existing network: {e}")
        
        # Create new internal network if it doesn't exist
        if self._worker_network is None:
            try:
                self._worker_network = await loop.run_in_executor(
                    None,
                    lambda: self._client.networks.create(
                        self.WORKER_NETWORK_NAME,
                        driver="bridge",
                        internal=True,  # No external internet access
                        check_duplicate=True,
                    )
                )
                logger.info(f"Created internal network: {self.WORKER_NETWORK_NAME}")
            except Exception as e:
                logger.error(f"Failed to create worker network: {e}")
                raise
    
    async def _connect_self_to_worker_network(self) -> None:
        """Connect the runner container to the worker network."""
        logger.info("Connecting runner to worker network...")
        
        loop = asyncio.get_event_loop()
        
        try:
            # Get the current container's ID
            import socket
            hostname = socket.gethostname()
            
            # Try to get container by hostname (container ID in Docker)
            try:
                current_container = await loop.run_in_executor(
                    None,
                    lambda: self._client.containers.get(hostname)
                )
            except Exception:
                # If running outside Docker, skip this step
                logger.info("Not running in Docker container, skipping network connection")
                return
            
            # Check if already connected
            current_container.reload()
            networks = current_container.attrs.get('NetworkSettings', {}).get('Networks', {})
            if self.WORKER_NETWORK_NAME in networks:
                logger.info("Runner already connected to worker network")
                return
            
            # Connect to the worker network
            await loop.run_in_executor(
                None,
                lambda: self._worker_network.connect(current_container)
            )
            logger.info("Runner connected to worker network")
            
        except Exception as e:
            logger.error(f"Failed to connect runner to worker network: {e}")
            # Don't raise - this might fail if running outside Docker
    
    async def _build_worker_image(self) -> None:
        """Build the worker Docker image."""
        logger.info("Building worker image...")
        
        worker_dir = os.path.join(os.path.dirname(__file__), "..", "worker")
        worker_dir = os.path.abspath(worker_dir)
        
        try:
            # Build in a thread pool to not block
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self._client.images.build(
                    path=worker_dir,
                    tag=self.worker_image,
                    rm=True,
                    forcerm=True,
                )
            )
            logger.info(f"Worker image '{self.worker_image}' built successfully")
        except Exception as e:
            logger.error(f"Failed to build worker image: {e}")
            raise
    
    async def _cleanup_old_workers(self) -> None:
        """Remove any leftover worker containers from previous runs."""
        logger.info("Cleaning up old worker containers...")
        
        loop = asyncio.get_event_loop()
        containers = await loop.run_in_executor(
            None,
            lambda: self._client.containers.list(
                all=True,
                filters={"name": "runner-worker-"}
            )
        )
        
        for container in containers:
            try:
                logger.info(f"Removing old container: {container.name}")
                await loop.run_in_executor(None, lambda c=container: c.remove(force=True))
            except Exception as e:
                logger.warning(f"Failed to remove container {container.name}: {e}")
    
    async def _spawn_workers(self) -> None:
        """Spawn all worker containers."""
        logger.info(f"Spawning {self.pool_size} worker containers...")
        
        tasks = []
        for i in range(self.pool_size):
            port = self.base_port + i
            tasks.append(self._spawn_single_worker(i, port))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Failed to spawn worker: {result}")
            elif result is not None:
                self.workers.append(result)
        
        if not self.workers:
            raise RuntimeError("Failed to spawn any worker containers")
    
    async def _spawn_single_worker(self, index: int, port: int) -> Optional[WorkerContainer]:
        """Spawn a single worker container."""
        container_name = f"runner-worker-{index}"
        
        try:
            loop = asyncio.get_event_loop()
            
            # Container configuration with security restrictions
            # Using internal network instead of network_mode="none" to allow
            # communication with the runner while still blocking external access
            container = await loop.run_in_executor(
                None,
                lambda: self._client.containers.run(
                    self.worker_image,
                    name=container_name,
                    detach=True,
                    network=self.WORKER_NETWORK_NAME,  # Internal network only
                    mem_limit=self.container_memory_limit,
                    nano_cpus=int(self.container_cpu_limit * 1e9),
                    read_only=False,  # Allow writing to /tmp
                    security_opt=["no-new-privileges:true"],
                    cap_drop=["ALL"],  # Drop all capabilities
                    pids_limit=50,  # Limit number of processes
                    environment={
                        "PYTHONDONTWRITEBYTECODE": "1",
                        "PYTHONUNBUFFERED": "1",
                    },
                )
            )
            
            # Get container IP address
            await asyncio.sleep(0.5)  # Brief wait for network assignment
            container.reload()
            container_ip = container.attrs['NetworkSettings']['Networks'][self.WORKER_NETWORK_NAME]['IPAddress']
            
            if not container_ip:
                raise RuntimeError(f"Container {container_name} has no IP address")
            
            logger.info(f"Worker {container_name} has IP {container_ip}")
            
            # Wait for container to be ready
            await self._wait_for_worker_ready(container_ip)
            
            logger.info(f"Worker {container_name} spawned and ready")
            return WorkerContainer(container=container, port=port, container_ip=container_ip)
        
        except Exception as e:
            logger.error(f"Failed to spawn worker {container_name}: {e}")
            return None
    
    async def _wait_for_worker_ready(self, container_ip: str, max_attempts: int = 30) -> None:
        """Wait for a worker container to be ready to accept requests."""
        url = f"http://{container_ip}:8000/health"
        
        for attempt in range(max_attempts):
            try:
                response = await self._http_client.get(url)
                if response.status_code == 200:
                    return
            except Exception:
                pass
            
            await asyncio.sleep(0.5)
        
        raise RuntimeError(f"Worker at {container_ip} failed to become ready")
    
    async def acquire(self) -> Optional[WorkerContainer]:
        """Acquire an available worker from the pool."""
        async with self._lock:
            for worker in self.workers:
                if not worker.busy:
                    worker.busy = True
                    worker.last_used = time.time()
                    worker.exec_start_time = time.time()
                    logger.debug(f"Acquired worker {worker.name}")
                    return worker
        
        logger.warning("No available workers in pool")
        return None
    
    async def release(self, worker: WorkerContainer) -> None:
        """Release a worker back to the pool."""
        async with self._lock:
            worker.busy = False
            worker.current_execution = None
            worker.exec_start_time = None
            logger.debug(f"Released worker {worker.name}")
    
    async def execute_code(
        self,
        code: str,
        timeout: int = 10,
        user_id: str = "anonymous"
    ) -> dict:
        """
        Execute code in an available worker container.
        
        Returns dict with stdout, stderr, return_code or error.
        """
        worker = await self.acquire()
        
        if worker is None:
            return {"error": "no available workers", "status_code": 503}
        
        # Create execution info
        execution_id = str(uuid.uuid4())[:8]
        execution = ExecutionInfo(
            execution_id=execution_id,
            user_id=user_id,
            code=code,
            worker_name=worker.name,
            start_time=time.time(),
        )
        worker.current_execution = execution
        
        # Emit execution start event
        await self._emit_event({
            "type": "execution_start",
            "execution_id": execution_id,
            "user_id": user_id,
            "code": code,
            "worker": worker.name,
        })
        
        # Also emit pool status update
        await self._emit_pool_status()
        
        success = False
        result = None
        
        try:
            response = await self._http_client.post(
                f"{worker.url}/execute",
                json={"code": code, "timeout": timeout},
                timeout=timeout + 5  # Extra time for HTTP overhead
            )
            
            result = response.json()
            
            if response.status_code == 200:
                success = True
            elif response.status_code == 408:
                result = {"error": "execution timed out", "status_code": 408}
            else:
                result = {"error": result.get("error", "unknown error"), "status_code": response.status_code}
        
        except httpx.TimeoutException:
            result = {"error": "execution timed out", "status_code": 408}
        except Exception as e:
            logger.error(f"Error executing code in worker {worker.name}: {e}")
            result = {"error": str(e), "status_code": 500}
        
        # Update execution info
        end_time = time.time()
        duration_ms = int((end_time - execution.start_time) * 1000)
        execution.end_time = end_time
        execution.duration_ms = duration_ms
        execution.success = success
        
        # Update statistics
        self.stats["total_executions"] += 1
        self.stats["total_exec_time_ms"] += duration_ms
        self.stats["total_lines"] += len(code.split('\n'))
        if success:
            self.stats["success_count"] += 1
        
        # Store in history
        self._execution_history.append(execution)
        if len(self._execution_history) > self._max_history:
            self._execution_history.pop(0)
        
        # Emit execution end event
        await self._emit_event({
            "type": "execution_end",
            "execution_id": execution_id,
            "duration": duration_ms,
            "success": success,
        })
        
        # Release worker and emit pool status
        await self.release(worker)
        await self._emit_pool_status()
        
        return result
    
    async def _emit_pool_status(self) -> None:
        """Emit current pool status to all listeners."""
        workers_status = []
        for worker in self.workers:
            worker_info = {
                "name": worker.name,
                "port": worker.port,
                "busy": worker.busy,
                "healthy": True,  # Assume healthy, real check is expensive
                "exec_start": worker.exec_start_time,
            }
            if worker.current_execution:
                worker_info["current_user"] = worker.current_execution.user_id
            workers_status.append(worker_info)
        
        await self._emit_event({
            "type": "pool_status",
            "workers": workers_status,
        })
    
    async def health_check(self) -> dict:
        """Check health of all workers in the pool."""
        results = {
            "total": len(self.workers),
            "available": 0,
            "busy": 0,
            "unhealthy": 0,
            "workers": []
        }
        
        for worker in self.workers:
            worker_status = {
                "name": worker.name,
                "port": worker.port,
                "busy": worker.busy,
                "healthy": False,
                "exec_start": worker.exec_start_time,
            }
            
            try:
                response = await self._http_client.get(
                    f"{worker.url}/health",
                    timeout=5.0
                )
                worker_status["healthy"] = response.status_code == 200
            except Exception:
                worker_status["healthy"] = False
            
            if worker_status["healthy"]:
                if worker.busy:
                    results["busy"] += 1
                else:
                    results["available"] += 1
            else:
                results["unhealthy"] += 1
            
            results["workers"].append(worker_status)
        
        return results
    
    def get_stats(self) -> dict:
        """Get execution statistics."""
        return {
            **self.stats,
            "avg_exec_time_ms": (
                self.stats["total_exec_time_ms"] / self.stats["total_executions"]
                if self.stats["total_executions"] > 0 else 0
            ),
            "avg_lines": (
                self.stats["total_lines"] / self.stats["total_executions"]
                if self.stats["total_executions"] > 0 else 0
            ),
            "success_rate": (
                self.stats["success_count"] / self.stats["total_executions"] * 100
                if self.stats["total_executions"] > 0 else 0
            ),
        }
    
    def get_execution_history(self, limit: int = 50) -> list[dict]:
        """Get recent execution history."""
        return [
            {
                "execution_id": e.execution_id,
                "user_id": e.user_id,
                "code": e.code,
                "worker": e.worker_name,
                "start_time": e.start_time,
                "duration_ms": e.duration_ms,
                "success": e.success,
            }
            for e in reversed(self._execution_history[-limit:])
        ]
    
    async def shutdown(self) -> None:
        """Gracefully shutdown all worker containers."""
        logger.info("Shutting down container pool...")
        
        if self._http_client:
            await self._http_client.aclose()
        
        loop = asyncio.get_event_loop()
        
        for worker in self.workers:
            try:
                logger.info(f"Stopping worker {worker.name}")
                await loop.run_in_executor(
                    None,
                    lambda w=worker: w.container.stop(timeout=5)
                )
                await loop.run_in_executor(
                    None,
                    lambda w=worker: w.container.remove(force=True)
                )
            except Exception as e:
                logger.warning(f"Error stopping worker {worker.name}: {e}")
        
        self.workers.clear()
        self._initialized = False
        logger.info("Container pool shutdown complete")


# Global pool instance
_pool: Optional[ContainerPool] = None


async def get_pool() -> ContainerPool:
    """Get or create the global container pool."""
    global _pool
    
    if _pool is None:
        _pool = ContainerPool(
            pool_size=int(os.environ.get("POOL_SIZE", "5")),
            base_port=int(os.environ.get("POOL_BASE_PORT", "9000")),
            container_memory_limit=os.environ.get("WORKER_MEMORY_LIMIT", "128m"),
            container_cpu_limit=float(os.environ.get("WORKER_CPU_LIMIT", "0.25")),
        )
        await _pool.initialize()
    
    return _pool


async def shutdown_pool() -> None:
    """Shutdown the global container pool."""
    global _pool
    
    if _pool is not None:
        await _pool.shutdown()
        _pool = None
