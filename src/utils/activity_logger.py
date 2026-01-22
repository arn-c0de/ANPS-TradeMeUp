"""
Activity Logger - Real-time agent activity tracking for dashboard
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Optional


class ActivityLogger:
    """Logger for tracking agent activities in real-time"""
    
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        self.activity_log = self.log_dir / "pipeline_activity.log"
        self.dashboard_log = self.log_dir / "dashboard.log"
        
    def log_activity(self, message: str, level: str = "INFO"):
        """
        Log agent activity to both activity and dashboard logs
        
        Args:
            message: Activity message
            level: Log level (INFO, SUCCESS, ERROR, PROCESSING, STARTING, COMPLETED)
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {level}: {message}\n"
        
        # Write to activity log (for live display)
        with open(self.activity_log, 'a', encoding='utf-8') as f:
            f.write(log_entry)
        
        # Also write to dashboard log (full details)
        with open(self.dashboard_log, 'a', encoding='utf-8') as f:
            f.write(log_entry)
        
        # Also print to console
        print(log_entry.strip())
    
    def log_agent_start(self, agent_name: str, phase: Optional[str] = None):
        """Log agent start"""
        phase_text = f" - Phase {phase}" if phase else ""
        self.log_activity(f"STARTING {agent_name}{phase_text}", "STARTING")
    
    def log_agent_processing(self, agent_name: str, item: str, current: int, total: int):
        """Log agent processing item"""
        self.log_activity(
            f"PROCESSING {agent_name}: {item} ({current}/{total})",
            "PROCESSING"
        )
    
    def log_agent_success(self, agent_name: str, count: int, duration: Optional[float] = None):
        """Log agent completion"""
        duration_text = f" in {duration:.2f}s" if duration else ""
        self.log_activity(
            f"SUCCESS {agent_name}: Processed {count} items{duration_text}",
            "SUCCESS"
        )
    
    def log_agent_error(self, agent_name: str, error: str):
        """Log agent error"""
        self.log_activity(f"ERROR {agent_name}: {error}", "ERROR")
    
    def log_pipeline_start(self, pipeline_name: str = "MVP Pipeline"):
        """Log pipeline start"""
        self.log_activity(f"=" * 60, "INFO")
        self.log_activity(f">> {pipeline_name} STARTED", "STARTING")
        self.log_activity(f"=" * 60, "INFO")
    
    def log_pipeline_complete(self, pipeline_name: str = "MVP Pipeline", duration: Optional[float] = None):
        """Log pipeline completion"""
        duration_text = f" in {duration:.2f}s" if duration else ""
        self.log_activity(f">> {pipeline_name} COMPLETED{duration_text}", "SUCCESS")
        self.log_activity(f"=" * 60, "INFO")
    
    def log_phase(self, phase_num: int, phase_name: str):
        """Log phase start"""
        self.log_activity(f"", "INFO")
        self.log_activity(f">> PHASE {phase_num}: {phase_name}", "INFO")
        self.log_activity(f"-" * 60, "INFO")
    
    def clear_logs(self):
        """Clear all log files"""
        if self.activity_log.exists():
            self.activity_log.unlink()
        if self.dashboard_log.exists():
            self.dashboard_log.unlink()


# Global instance
activity_logger = ActivityLogger()
