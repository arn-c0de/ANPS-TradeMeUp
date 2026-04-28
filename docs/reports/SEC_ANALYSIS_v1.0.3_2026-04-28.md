# Security Analysis Report: ANPS-TradeMeUp
**Project Version:** 1.0.3
**Report Date:** 2026-04-28
**Analyst:** CyberSec Senior Auditor
**Status:** ⚠️ CRITICAL VULNERABILITIES IDENTIFIED

---

## 1. Executive Summary
The security audit of the **ANPS-TradeMeUp** codebase has revealed several **Critical** and **High-risk** vulnerabilities that allow for **Remote Code Execution (RCE)** and **Arbitrary Command Injection**. The system, while functionally robust, lacks basic input sanitization and secure configuration management in its GUI and Agent components.

**Immediate Action Required:** Disable Dash Debug mode and refactor the subprocess management in the Control Tab.

---

## 2. Vulnerability Overview Matrix

| ID | Vulnerability | Severity | Target Component | Impact |
|:---|:---|:---|:---|:---|
| **V-01** | Unauthenticated RCE (Dash Debugger) | **CRITICAL** | `src/gui/app.py` | Full Host Compromise |
| **V-02** | OS Command Injection | **HIGH** | `src/gui/tabs/control.py` | Arbitrary System Commands |
| **V-03** | Environment Variable Injection | **HIGH** | `src/gui/tabs/settings.py` | Config Hijacking/RCE |
| **V-04** | Insecure Deserialization (Pickle) | **HIGH** | `src/agents/prediction_agent.py` | Code Execution via Model |
| **V-05** | Hardcoded Credentials | **MEDIUM** | Multiple Scripts/Docs | Credential Leakage |
| **V-06** | Second-Order SQL Injection | **MEDIUM** | `src/gui/tabs/databases.py` | Database Compromise |

---

## 3. Detailed Technical Findings

### V-01: Unauthenticated RCE via Dash Debugger
- **Location:** `src/gui/app.py:130`
- **Description:** The application starts with `debug=True` and binds to `host="0.0.0.0"`.
- **Exploit:** The Werkzeug interactive debugger is exposed on all network interfaces. An attacker can access the `/` or any error page, open the console, and execute arbitrary Python code.
- **Remediation:** 
  ```python
  # Change to:
  app.run(debug=False, host="127.0.0.1", port=8050)
  ```

### V-02: OS Command Injection in Agent Control
- **Location:** `src/gui/tabs/control.py` -> `open_terminal_with_command`
- **Description:** The function uses `subprocess.Popen(..., shell=True)` with string interpolation. In `run_selective_backfill`, the `batch_size` (taken from a Dash slider/input) is formatted directly into a shell command.
- **Exploit:** A forged callback request can send a string like `"50; touch /tmp/pwned"` as `batch_size`.
- **Remediation:** Remove `shell=True`, use list-based arguments for `subprocess`, and strictly type-validate all inputs.

### V-03: Environment Variable Injection
- **Location:** `src/gui/tabs/settings.py` -> `_save_llm_settings`
- **Description:** The system writes provider and model names directly to `.env.local` without sanitizing newlines (`\n`).
- **Exploit:** An attacker can set a model name to `gpt-4\nMALICIOUS_VAR=VALUE` to hijack configurations.
- **Remediation:** Use a whitelist for allowed values and strip all newline characters.

### V-04: Insecure Deserialization (Pickle)
- **Location:** `src/agents/prediction_agent.py:76`
- **Description:** The agent uses `pickle.load(f)` to load XGBoost models from disk.
- **Exploit:** If an attacker can replace a `.pkl` file in the `models/` directory, they gain full code execution when the agent initializes.
- **Remediation:** Switch to native XGBoost `load_model` (JSON/UBJSON) which does not execute arbitrary code.

### V-05: Hardcoded Credentials & PGPASSWORD Leakage
- **Location:** `.env.example`, `scripts/db/setup_postgresql_from_backup.sh`
- **Description:** 
    1. Example keys are present in documentation.
    2. Shell scripts export `PGPASSWORD` directly, making it visible in process lists.
- **Remediation:** Use `.pgpass` or environment variables injected via secure secrets management.

---

## 4. Architectural Recommendations

1. **Input Validation:** Implement a global input validation layer for all Dash callbacks. Never trust types coming from the client.
2. **Subprocess Security:** Replace all `os.system` and `shell=True` calls with secure list-based `subprocess.Popen` calls.
3. **Database Hardening:** Ensure all queries, especially those involving schema changes or bulk deletes in `databases.py`, use SQLAlchemy's parameter binding.
4. **Log Redaction:** Audit `activity_logger` to ensure it does not leak sensitive environment data during error tracebacks.

---
**Analyst Note:** This system should NOT be exposed to any untrusted network until V-01 and V-02 are remediated.
