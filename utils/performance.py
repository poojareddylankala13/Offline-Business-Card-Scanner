import time
import psutil
import os
from contextlib import contextmanager
from typing import Dict, Any, Generator
from utils.logger import get_logger

logger = get_logger("performance")

class Timer:
    """
    Simple class to measure elapsed time. Can be used as a context manager or standalone.
    """
    def __init__(self):
        self.start_time = None
        self.end_time = None
        self.elapsed = None

    def start(self):
        self.start_time = time.perf_counter()
        self.end_time = None
        self.elapsed = None
        return self

    def stop(self):
        if self.start_time is None:
            raise ValueError("Timer was never started.")
        self.end_time = time.perf_counter()
        self.elapsed = self.end_time - self.start_time
        return self.elapsed

@contextmanager
def measure_time() -> Generator[Timer, None, None]:
    """
    Context manager to measure execution time of a code block.
    """
    timer = Timer()
    timer.start()
    try:
        yield timer
    finally:
        timer.stop()

def get_process_resources() -> Dict[str, Any]:
    """
    Returns current process CPU and memory metrics.
    """
    try:
        process = psutil.Process(os.getpid())
        # Call cpu_percent once to initialize or get current usage since last call
        # In a short-lived script, process.cpu_percent() might return 0.0 unless given an interval,
        # but in Streamlit we can use it regularly or just read the system CPU.
        cpu_usage_proc = process.cpu_percent(interval=None)
        
        # Memory info (RSS in bytes)
        mem_info = process.memory_info()
        mem_rss_mb = mem_info.rss / (1024 * 1024)
        
        # System-wide metrics
        sys_cpu = psutil.cpu_percent(interval=None)
        sys_mem = psutil.virtual_memory()
        
        return {
            "process_cpu_percent": cpu_usage_proc,
            "process_memory_mb": round(mem_rss_mb, 2),
            "system_cpu_percent": sys_cpu,
            "system_memory_percent": sys_mem.percent,
            "system_memory_available_mb": round(sys_mem.available / (1024 * 1024), 2)
        }
    except Exception as e:
        logger.error(f"Failed to gather resource usage metrics: {e}")
        return {
            "process_cpu_percent": 0.0,
            "process_memory_mb": 0.0,
            "system_cpu_percent": 0.0,
            "system_memory_percent": 0.0,
            "system_memory_available_mb": 0.0
        }

def log_metrics(stage: str, timer: Timer, resources: Dict[str, Any]):
    """
    Logs the performance metrics of a specific processing stage.
    """
    elapsed = timer.elapsed if timer.elapsed is not None else 0.0
    logger.info(
        f"Stage [{stage}] completed in {elapsed:.3f}s. "
        f"Process Memory: {resources.get('process_memory_mb', 0)}MB | "
        f"System CPU: {resources.get('system_cpu_percent', 0)}% | "
        f"System Memory: {resources.get('system_memory_percent', 0)}%"
    )
