"""
Process utilities for robust subprocess management
"""
import sys
import os
import subprocess
from pathlib import Path
from typing import Optional, Tuple, List


def get_python_executable() -> str:
    """
    Get the correct Python executable path for the current environment.
    
    Returns:
        str: Path to Python executable
        
    Raises:
        RuntimeError: If Python executable cannot be found
    """
    # Use current interpreter (works for venv, conda, system Python)
    python_exe = sys.executable
    
    if not python_exe or not os.path.isfile(python_exe):
        raise RuntimeError(
            "Cannot locate Python executable. "
            f"sys.executable returned: {python_exe}"
        )
    
    return python_exe


def get_project_root() -> Path:
    """
    Get the project root directory.
    
    Returns:
        Path: Project root directory
    """
    # Assuming this file is in src/utils/
    return Path(__file__).parent.parent.parent


def validate_script_path(script_path: str) -> Tuple[bool, str]:
    """
    Validate that a script exists and return absolute path.
    
    Args:
        script_path: Relative or absolute path to script
        
    Returns:
        Tuple of (success: bool, path_or_error: str)
    """
    script = Path(script_path)
    
    # Try absolute path first
    if script.is_absolute() and script.exists():
        return True, str(script)
    
    # Try relative to project root
    root = get_project_root()
    full_path = root / script
    
    if full_path.exists():
        return True, str(full_path)
    
    return False, f"Script not found: {script_path}"


def start_background_process(
    script_path: str,
    args: Optional[List[str]] = None,
    log_file: Optional[Path] = None,
    create_console: bool = False
) -> Tuple[bool, Optional[subprocess.Popen], str]:
    """
    Start a Python script as background process with robust error handling.

    Args:
        script_path: Path to Python script (relative to project root)
        args: Optional command-line arguments
        log_file: Optional log file for output redirection
        create_console: Whether to create new console (Windows only)

    Returns:
        Tuple of (success: bool, process: Optional[Popen], message: str)
    """
    try:
        # Get Python executable
        python_exe = get_python_executable()

        # Validate script
        success, result = validate_script_path(script_path)
        if not success:
            return False, None, result

        script_abs = result

        # Build command
        cmd = [python_exe, "-u", script_abs]  # -u for unbuffered output
        if args:
            cmd.extend(args)

        # Get project root for working directory
        cwd = get_project_root()

        # Prepare process arguments
        popen_kwargs = {
            "cwd": str(cwd),
            "text": True,
            # Explicitly inherit environment to ensure venv is available
            "env": os.environ.copy()
        }

        # Handle output redirection
        if log_file:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            f = open(log_file, "w")
            popen_kwargs["stdout"] = f
            popen_kwargs["stderr"] = subprocess.STDOUT
        else:
            popen_kwargs["stdout"] = subprocess.PIPE
            popen_kwargs["stderr"] = subprocess.STDOUT

        # Windows: create new console if requested
        # Note: When creating new console, subprocess inherits parent environment
        if create_console and os.name == 'nt':
            popen_kwargs["creationflags"] = subprocess.CREATE_NEW_CONSOLE

        # Start process
        process = subprocess.Popen(cmd, **popen_kwargs)

        return True, process, f"Process started successfully (PID: {process.pid})"

    except FileNotFoundError as e:
        return False, None, f"Python executable or script not found: {e}"
    except PermissionError as e:
        return False, None, f"Permission denied when starting process: {e}"
    except Exception as e:
        return False, None, f"Failed to start process: {type(e).__name__}: {e}"


def stop_process(pid: int) -> Tuple[bool, str]:
    """
    Stop a running process by PID.
    
    Args:
        pid: Process ID
        
    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        import psutil
        
        try:
            process = psutil.Process(pid)
            process.terminate()
            
            # Wait up to 5 seconds for graceful termination
            try:
                process.wait(timeout=5)
                return True, f"Process {pid} terminated successfully"
            except psutil.TimeoutExpired:
                # Force kill if it doesn't terminate
                process.kill()
                return True, f"Process {pid} forcefully killed"
                
        except psutil.NoSuchProcess:
            return False, f"Process {pid} not found (may have already stopped)"
        except psutil.AccessDenied:
            return False, f"Access denied when trying to stop process {pid}"
            
    except ImportError:
        return False, "psutil library not installed - cannot stop processes"
    except Exception as e:
        return False, f"Error stopping process: {type(e).__name__}: {e}"


def check_process_running(pid: Optional[int]) -> bool:
    """
    Check if a process is still running.
    
    Args:
        pid: Process ID (or None)
        
    Returns:
        bool: True if process is running, False otherwise
    """
    if not pid:
        return False
    
    try:
        import psutil
        return psutil.pid_exists(pid)
    except ImportError:
        # Fallback: try to send signal 0 (no-op, just checks existence)
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False
