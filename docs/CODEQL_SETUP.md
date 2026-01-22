# CodeQL Setup Guide

## GitHub Actions (Automated)
The CodeQL workflow is configured in `.github/workflows/codeql-analysis.yml` and will run automatically on GitHub.

## Local CLI Installation

### Option 1: Using GitHub CLI
```bash
# Install CodeQL CLI
gh extension install github/gh-codeql

# Or download directly
# https://github.com/github/codeql-cli-binaries/releases
```

### Option 2: Manual Installation
1. Download CodeQL CLI from: https://github.com/github/codeql-cli-binaries/releases
2. Extract to a directory (e.g., `C:\codeql`)
3. Add to PATH: `C:\codeql\codeql`
4. Clone CodeQL queries:
```bash
git clone https://github.com/github/codeql.git C:\codeql-repo
```

### Running Local Analysis
```bash
# Create CodeQL database
codeql database create python-db --language=python --source-root=.

# Run analysis
codeql database analyze python-db --format=sarif-latest --output=results.sarif

# View results
codeql database analyze python-db --format=text
```

## Custom Queries
You can customize the queries by modifying the workflow file to include:
```yaml
queries: security-extended,security-and-quality
```

## Common Security Checks
CodeQL for Python detects:
- SQL injection vulnerabilities
- Command injection
- Path traversal
- XSS vulnerabilities
- Insecure deserialization
- Hardcoded credentials
- And many more...
