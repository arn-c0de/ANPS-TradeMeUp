"""
Task Queue Manager for GUI Actions
Handles asynchronous task execution with queuing to prevent server overload
"""

import logging
import queue
import threading
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, Optional

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
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result: Any = None
    error: Exception | None = None
    priority: int = 0  # Higher = more important

    def __lt__(self, other):
        """For priority queue sorting"""
        return self.priority > other.priority  # Higher priority first


class TaskQueueManager:
    """
    Manages task execution with queuing and concurrency control using threading.
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
        self.queues: dict[str, queue.Queue] = defaultdict(lambda: queue.Queue(maxsize=max_queue_size))

        # Currently running tasks
        self.running_tasks: dict[str, Task] = {}
        self.running_tasks_lock = threading.Lock()

        # Completed tasks history (last 100)
        self.completed_tasks: list[Task] = []
        self.completed_tasks_lock = threading.Lock()
        self.max_history = 100

        # Task type workers (one worker thread per task type)
        self.workers: dict[str, threading.Thread] = {}
        self.workers_lock = threading.Lock()

        # Statistics
        self.stats = {
            "total_tasks": 0,
            "completed": 0,
            "failed": 0,
            "cancelled": 0,
            "avg_execution_time": 0.0
        }
        self.stats_lock = threading.Lock()

        # Running flag
        self._running = True

        logger.info(f"TaskQueueManager initialized: max_concurrent={max_concurrent_tasks}, max_queue={max_queue_size}")

    def start(self):
        """Start the task queue manager"""
        if not self._running:
            self._running = True
            logger.info("TaskQueueManager started")

    def stop(self):
        """Stop the task queue manager and wait for running tasks"""
        self._running = False

        # Cancel all pending tasks
        for task_type, q in self.queues.items():
            while not q.empty():
                try:
                    task = q.get_nowait()
                    task.status = TaskStatus.CANCELLED
                    with self.stats_lock:
                        self.stats["cancelled"] += 1
                except queue.Empty:
                    break

        # Wait for workers to finish
        with self.workers_lock:
            for worker in self.workers.values():
                if worker.is_alive():
                    worker.join(timeout=5.0)

        logger.info("TaskQueueManager stopped")

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
        q = self.queues[task_type]

        # Try to add task to queue
        try:
            q.put_nowait(task)
            with self.stats_lock:
                self.stats["total_tasks"] += 1
            logger.info(f"Task {task_id} ({task_type}) added to queue (priority={priority})")
        except queue.Full:
            logger.warning(f"Queue full for {task_type}, task {task_id} dropped")
            return task_id

        # Start worker if not running
        with self.workers_lock:
            if task_type not in self.workers or not self.workers[task_type].is_alive():
                worker = threading.Thread(
                    target=self._worker,
                    args=(task_type,),
                    daemon=True,
                    name=f"TaskWorker-{task_type}"
                )
                worker.start()
                self.workers[task_type] = worker
                logger.info(f"Started worker thread for {task_type}")

        return task_id

    def _worker(self, task_type: str):
        """
        Worker that processes tasks from queue sequentially
        
        Args:
            task_type: Type of tasks this worker handles
        """
        logger.info(f"Worker started for task type: {task_type}")
        q = self.queues[task_type]

        while self._running:
            try:
                # Get next task (wait up to 1 second)
                try:
                    task = q.get(timeout=1.0)
                except queue.Empty:
                    continue

                # Execute task
                self._execute_task(task)
                q.task_done()

            except Exception as e:
                logger.error(f"Worker error for {task_type}: {e}", exc_info=True)

        logger.info(f"Worker stopped for task type: {task_type}")

    def _execute_task(self, task: Task):
        """
        Execute a single task
        
        Args:
            task: Task to execute
        """
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()

        with self.running_tasks_lock:
            self.running_tasks[task.task_id] = task

        logger.info(f"Executing task {task.task_id} ({task.task_type})")

        try:
            # Execute function (synchronous)
            result = task.function(*task.args, **task.kwargs)

            task.result = result
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()

            # Update statistics
            with self.stats_lock:
                self.stats["completed"] += 1
                execution_time = (task.completed_at - task.started_at).total_seconds()
                self._update_avg_execution_time(execution_time)

            logger.info(f"Task {task.task_id} completed in {execution_time:.2f}s")

        except Exception as e:
            task.error = e
            task.status = TaskStatus.FAILED
            task.completed_at = datetime.now()

            with self.stats_lock:
                self.stats["failed"] += 1

            logger.error(f"Task {task.task_id} failed: {e}", exc_info=True)

        finally:
            # Move to history
            with self.running_tasks_lock:
                self.running_tasks.pop(task.task_id, None)

            with self.completed_tasks_lock:
                self.completed_tasks.append(task)

                # Limit history size
                if len(self.completed_tasks) > self.max_history:
                    self.completed_tasks.pop(0)

    def _update_avg_execution_time(self, new_time: float):
        """Update average execution time with exponential moving average"""
        alpha = 0.2  # Smoothing factor
        current_avg = self.stats["avg_execution_time"]
        self.stats["avg_execution_time"] = alpha * new_time + (1 - alpha) * current_avg

    def get_task_status(self, task_id: str) -> TaskStatus | None:
        """Get status of a task by ID"""
        # Check running tasks
        with self.running_tasks_lock:
            if task_id in self.running_tasks:
                return self.running_tasks[task_id].status

        # Check completed tasks
        with self.completed_tasks_lock:
            for task in reversed(self.completed_tasks):
                if task.task_id == task_id:
                    return task.status

        return None

    def get_task_result(self, task_id: str) -> Any:
        """Get result of a completed task"""
        # Check running tasks
        with self.running_tasks_lock:
            if task_id in self.running_tasks:
                task = self.running_tasks[task_id]
                if task.status == TaskStatus.COMPLETED:
                    return task.result
                return None

        # Check completed tasks
        with self.completed_tasks_lock:
            for task in reversed(self.completed_tasks):
                if task.task_id == task_id:
                    if task.status == TaskStatus.COMPLETED:
                        return task.result
                    return None

        return None

    def get_queue_stats(self) -> dict[str, Any]:
        """Get current queue statistics"""
        queue_sizes = {task_type: q.qsize() for task_type, q in self.queues.items()}

        with self.stats_lock:
            stats_copy = self.stats.copy()

        with self.running_tasks_lock:
            running_count = len(self.running_tasks)

        return {
            **stats_copy,
            "running_tasks": running_count,
            "queue_sizes": queue_sizes,
            "total_queued": sum(queue_sizes.values())
        }

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending task (can't cancel running tasks)"""
        for task_type, q in self.queues.items():
            # Search through queue
            temp_tasks = []
            found = False

            while not q.empty():
                try:
                    task = q.get_nowait()
                    if task.task_id == task_id:
                        task.status = TaskStatus.CANCELLED
                        with self.stats_lock:
                            self.stats["cancelled"] += 1
                        found = True
                        logger.info(f"Task {task_id} cancelled")
                    else:
                        temp_tasks.append(task)
                except queue.Empty:
                    break

            # Re-add tasks
            for task in temp_tasks:
                try:
                    q.put_nowait(task)
                except queue.Full:
                    logger.warning(f"Could not re-add task {task.task_id} to queue")

            if found:
                return True

        return False


# Global task queue manager instance
_task_queue_manager: TaskQueueManager | None = None
_task_queue_lock = threading.Lock()


def get_task_queue() -> TaskQueueManager:
    """Get or create global task queue manager"""
    global _task_queue_manager

    if _task_queue_manager is None:
        with _task_queue_lock:
            # Double-check locking pattern
            if _task_queue_manager is None:
                _task_queue_manager = TaskQueueManager(max_concurrent_tasks=3)
                _task_queue_manager.start()

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
    queue_mgr = get_task_queue()
    return queue_mgr.add_task(task_type, function, *args, priority=priority, **kwargs)
