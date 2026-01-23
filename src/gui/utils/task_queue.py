"""
Task Queue Manager for GUI Actions
Handles asynchronous task execution with queuing to prevent server overload
"""

import asyncio
import logging
import time
from typing import Callable, Any, Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import uuid
from collections import defaultdict

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Task execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Task:
    """Represents a queued task"""
    task_id: str
    task_type: str  # e.g., "refresh_prediction", "load_news", etc.
    function: Callable
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Any = None
    error: Optional[Exception] = None
    priority: int = 0  # Higher = more important
    
    def __lt__(self, other):
        """For priority queue sorting"""
        return self.priority > other.priority  # Higher priority first


class TaskQueueManager:
    """
    Manages task execution with queuing and concurrency control.
    Ensures tasks are executed sequentially to prevent server overload.
    """
    
    def __init__(self, max_concurrent_tasks: int = 3, max_queue_size: int = 50):
        """
        Initialize task queue manager
        
        Args:
            max_concurrent_tasks: Maximum number of tasks running simultaneously
            max_queue_size: Maximum number of tasks in queue
        """
        self.max_concurrent_tasks = max_concurrent_tasks
        self.max_queue_size = max_queue_size
        
        # Queue for pending tasks (FIFO per task type)
        self.queues: Dict[str, asyncio.Queue] = defaultdict(lambda: asyncio.Queue())
        
        # Currently running tasks
        self.running_tasks: Dict[str, Task] = {}
        
        # Completed tasks history (last 100)
        self.completed_tasks: list[Task] = []
        self.max_history = 100
        
        # Task type workers (one worker per task type)
        self.workers: Dict[str, asyncio.Task] = {}
        
        # Statistics
        self.stats = {
            "total_tasks": 0,
            "completed": 0,
            "failed": 0,
            "cancelled": 0,
            "avg_execution_time": 0.0
        }
        
        # Event loop
        self._loop = None
        self._running = False
        
        logger.info(f"TaskQueueManager initialized: max_concurrent={max_concurrent_tasks}, max_queue={max_queue_size}")
    
    async def start(self):
        """Start the task queue manager"""
        if self._running:
            return
        
        self._running = True
        logger.info("TaskQueueManager started")
    
    async def stop(self):
        """Stop the task queue manager and wait for running tasks"""
        self._running = False
        
        # Cancel all pending tasks
        for task_type, queue in self.queues.items():
            while not queue.empty():
                try:
                    task = queue.get_nowait()
                    task.status = TaskStatus.CANCELLED
                    self.stats["cancelled"] += 1
                except asyncio.QueueEmpty:
                    break
        
        # Stop workers
        for worker in self.workers.values():
            worker.cancel()
        
        # Wait for running tasks
        if self.running_tasks:
            await asyncio.gather(*[asyncio.create_task(self._wait_for_task(t)) for t in self.running_tasks.values()], return_exceptions=True)
        
        logger.info("TaskQueueManager stopped")
    
    async def _wait_for_task(self, task: Task):
        """Wait for a task to complete"""
        timeout = 30  # 30 second timeout
        start = time.time()
        while task.status == TaskStatus.RUNNING and (time.time() - start) < timeout:
            await asyncio.sleep(0.1)
    
    def add_task(
        self, 
        task_type: str,
        function: Callable,
        *args,
        priority: int = 0,
        **kwargs
    ) -> str:
        """
        Add a task to the queue
        
        Args:
            task_type: Type of task (used for grouping and worker assignment)
            function: Function to execute
            *args: Positional arguments for function
            priority: Task priority (higher = executed first)
            **kwargs: Keyword arguments for function
            
        Returns:
            task_id: Unique task identifier
        """
        task_id = str(uuid.uuid4())
        
        task = Task(
            task_id=task_id,
            task_type=task_type,
            function=function,
            args=args,
            kwargs=kwargs,
            priority=priority
        )
        
        # Add to appropriate queue
        queue = self.queues[task_type]
        
        # Check queue size
        if queue.qsize() >= self.max_queue_size:
            logger.warning(f"Queue full for {task_type}, dropping oldest task")
            try:
                old_task = queue.get_nowait()
                old_task.status = TaskStatus.CANCELLED
                self.stats["cancelled"] += 1
            except asyncio.QueueEmpty:
                pass
        
        # Add task to queue (using put_nowait for synchronous operation)
        try:
            queue.put_nowait(task)
            self.stats["total_tasks"] += 1
            logger.info(f"Task {task_id} ({task_type}) added to queue (priority={priority})")
        except asyncio.QueueFull:
            logger.error(f"Failed to add task {task_id} to queue (full)")
            return None
        
        # Start worker if not running
        if task_type not in self.workers or self.workers[task_type].done():
            self.workers[task_type] = asyncio.create_task(self._worker(task_type))
        
        return task_id
    
    async def _worker(self, task_type: str):
        """
        Worker that processes tasks from queue sequentially
        
        Args:
            task_type: Type of tasks this worker handles
        """
        logger.info(f"Worker started for task type: {task_type}")
        queue = self.queues[task_type]
        
        while self._running:
            try:
                # Get next task (wait up to 1 second)
                try:
                    task = await asyncio.wait_for(queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue
                
                # Execute task
                await self._execute_task(task)
                
            except asyncio.CancelledError:
                logger.info(f"Worker for {task_type} cancelled")
                break
            except Exception as e:
                logger.error(f"Worker error for {task_type}: {e}", exc_info=True)
        
        logger.info(f"Worker stopped for task type: {task_type}")
    
    async def _execute_task(self, task: Task):
        """
        Execute a single task
        
        Args:
            task: Task to execute
        """
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()
        self.running_tasks[task.task_id] = task
        
        logger.info(f"Executing task {task.task_id} ({task.task_type})")
        
        try:
            # Execute function (support both sync and async)
            if asyncio.iscoroutinefunction(task.function):
                result = await task.function(*task.args, **task.kwargs)
            else:
                # Run sync function in executor to prevent blocking
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, lambda: task.function(*task.args, **task.kwargs))
            
            task.result = result
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            
            # Update statistics
            self.stats["completed"] += 1
            execution_time = (task.completed_at - task.started_at).total_seconds()
            self._update_avg_execution_time(execution_time)
            
            logger.info(f"Task {task.task_id} completed in {execution_time:.2f}s")
            
        except Exception as e:
            task.error = e
            task.status = TaskStatus.FAILED
            task.completed_at = datetime.now()
            self.stats["failed"] += 1
            
            logger.error(f"Task {task.task_id} failed: {e}", exc_info=True)
        
        finally:
            # Move to history
            self.running_tasks.pop(task.task_id, None)
            self.completed_tasks.append(task)
            
            # Limit history size
            if len(self.completed_tasks) > self.max_history:
                self.completed_tasks.pop(0)
    
    def _update_avg_execution_time(self, new_time: float):
        """Update average execution time with exponential moving average"""
        alpha = 0.2  # Smoothing factor
        current_avg = self.stats["avg_execution_time"]
        self.stats["avg_execution_time"] = alpha * new_time + (1 - alpha) * current_avg
    
    def get_task_status(self, task_id: str) -> Optional[TaskStatus]:
        """Get status of a task by ID"""
        # Check running tasks
        if task_id in self.running_tasks:
            return self.running_tasks[task_id].status
        
        # Check completed tasks
        for task in reversed(self.completed_tasks):
            if task.task_id == task_id:
                return task.status
        
        return None
    
    def get_task_result(self, task_id: str) -> Any:
        """Get result of a completed task"""
        # Check running tasks
        if task_id in self.running_tasks:
            task = self.running_tasks[task_id]
            if task.status == TaskStatus.COMPLETED:
                return task.result
            return None
        
        # Check completed tasks
        for task in reversed(self.completed_tasks):
            if task.task_id == task_id:
                if task.status == TaskStatus.COMPLETED:
                    return task.result
                return None
        
        return None
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """Get current queue statistics"""
        queue_sizes = {task_type: queue.qsize() for task_type, queue in self.queues.items()}
        
        return {
            **self.stats,
            "running_tasks": len(self.running_tasks),
            "queue_sizes": queue_sizes,
            "total_queued": sum(queue_sizes.values())
        }
    
    def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending or running task"""
        # Can't cancel running tasks, only pending ones
        for task_type, queue in self.queues.items():
            # Search through queue (inefficient but rare operation)
            temp_tasks = []
            found = False
            
            while not queue.empty():
                try:
                    task = queue.get_nowait()
                    if task.task_id == task_id:
                        task.status = TaskStatus.CANCELLED
                        self.stats["cancelled"] += 1
                        found = True
                        logger.info(f"Task {task_id} cancelled")
                    else:
                        temp_tasks.append(task)
                except asyncio.QueueEmpty:
                    break
            
            # Re-add tasks
            for task in temp_tasks:
                try:
                    queue.put_nowait(task)
                except asyncio.QueueFull:
                    pass
            
            if found:
                return True
        
        return False


# Global task queue manager instance
_task_queue_manager: Optional[TaskQueueManager] = None


def get_task_queue() -> TaskQueueManager:
    """Get or create global task queue manager"""
    global _task_queue_manager
    
    if _task_queue_manager is None:
        _task_queue_manager = TaskQueueManager(max_concurrent_tasks=3)
        # Start the manager in the background
        try:
            loop = asyncio.get_event_loop()
            if not loop.is_running():
                asyncio.run(_task_queue_manager.start())
            else:
                asyncio.create_task(_task_queue_manager.start())
        except RuntimeError:
            # No event loop, will start on first task
            pass
    
    return _task_queue_manager


def add_gui_task(task_type: str, function: Callable, *args, priority: int = 0, **kwargs) -> str:
    """
    Convenience function to add a GUI task to the queue
    
    Args:
        task_type: Type of task
        function: Function to execute
        *args: Positional arguments
        priority: Task priority
        **kwargs: Keyword arguments
        
    Returns:
        task_id: Unique task identifier
    """
    queue = get_task_queue()
    return queue.add_task(task_type, function, *args, priority=priority, **kwargs)
