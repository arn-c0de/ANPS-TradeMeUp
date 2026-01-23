# Process Utilities Documentation

## Overview
The `src/utils/process_utils.py` module provides robust subprocess management for the TradeMeUp GUI, replacing fragile hardcoded paths with environment-aware process handling.

## Key Features

### 🔧 Robust Python Executable Detection
- Uses `sys.executable` to automatically detect the active Python interpreter
- Works with venv, conda, system Python, and any other environment
- Eliminates hardcoded paths like `venv/Scripts/python.exe`

### ✅ Script Path Validation
- Validates script existence before attempting to run
- Supports both absolute and relative paths
- Provides clear error messages when scripts are missing

### 🚀 Background Process Management
- Unified API for starting background processes
- Optional output redirection to log files
- Cross-platform console creation support
- Comprehensive error handling with user-friendly messages

### ⏹️ Process Control
- Graceful process termination with timeout
- Automatic fallback to force kill if needed
- Process existence checking
- Detailed status messages for all operations

## Usage Examples

### Starting a Background Process
```python
from src.utils.process_utils import start_background_process

success, process, message = start_background_process(
    script_path="scripts/run_mvp_pipeline.py",
    args=["--verbose"],
    log_file=Path("logs/pipeline.log"),
    create_console=False
)

if success:
    print(f"Started process {process.pid}")
else:
    print(f"Failed: {message}")
```

### Stopping a Process
```python
from src.utils.process_utils import stop_process

success, message = stop_process(pid=12345)
print(message)  # "Process 12345 terminated successfully"
```

### Checking Process Status
```python
from src.utils.process_utils import check_process_running

if check_process_running(pid=12345):
    print("Process is still running")
```

## Error Handling

All functions return tuples with:
1. **Success flag** (bool): Whether operation succeeded
2. **Result** (process/None): The Popen object or None on failure
3. **Message** (str): Human-readable status or error message

Example error messages:
- `"Script not found: scripts/missing.py"`
- `"Python executable or script not found: [Errno 2] ..."`
- `"Permission denied when starting process: [Errno 13] ..."`
- `"Process 12345 not found (may have already stopped)"`

## GUI Integration

The GUI (`src/gui/app.py`) now uses these utilities in:
- **Continuous Pipeline Control**: `control_continuous_pipeline()`
- **Full Pipeline Execution**: `run_full_pipeline()`
- **Quick Test Execution**: `run_quick_test()`

### Benefits
✅ **No more hardcoded paths** - works in any environment  
✅ **Better error messages** - users see helpful troubleshooting steps  
✅ **Proper logging** - all failures are logged with context  
✅ **Cross-platform** - handles Windows/Linux/Mac differences  
✅ **Testable** - clean separation of concerns  

## Dependencies

- **Standard library**: `sys`, `os`, `subprocess`, `pathlib`
- **Optional**: `psutil` (for robust process management)
  - If psutil is not installed, falls back to basic `os.kill()`

## Error Recovery

When a process fails to start, the GUI now displays:
```
[12:34:56] STARTUP ERROR
Failed to start pipeline: Script not found: scripts/run_mvp_pipeline.py

Please check:
  1. Python environment is activated
  2. Script exists: scripts/run_mvp_pipeline.py
  3. Required dependencies are installed
```

This gives users clear actionable steps to resolve issues.

## Testing

To test process utilities:
```python
from src.utils.process_utils import (
    get_python_executable,
    validate_script_path,
    start_background_process
)

# Test 1: Get Python executable
python_exe = get_python_executable()
print(f"Python: {python_exe}")

# Test 2: Validate script path
success, path = validate_script_path("scripts/run_mvp_pipeline.py")
print(f"Valid: {success}, Path: {path}")

# Test 3: Start a simple process
success, proc, msg = start_background_process(
    "scripts/run_ingestion.py",
    args=["--limit", "5"]
)
print(f"Started: {success}, Message: {msg}")
```

## Migration Notes

### Old Code (Fragile)
```python
import subprocess
PROJECT_ROOT = Path(__file__).parent.parent.parent
python_exe = os.path.join(PROJECT_ROOT, "venv", "Scripts", "python.exe")
process = subprocess.Popen([python_exe, script])  # May fail silently
```

### New Code (Robust)
```python
from src.utils.process_utils import start_background_process

success, process, message = start_background_process(
    script_path="scripts/my_script.py",
    args=[]
)

if not success:
    # Show error to user with helpful message
    print(f"Error: {message}")
```

## Future Enhancements

Potential improvements:
- [ ] Add process queue/job scheduler
- [ ] Implement process monitoring callbacks
- [ ] Add resource usage tracking (CPU/memory)
- [ ] Support for process groups
- [ ] Automatic restart on failure
- [ ] Process output streaming to GUI

---

**Last Updated**: January 23, 2026  
**Version**: 1.1.0
