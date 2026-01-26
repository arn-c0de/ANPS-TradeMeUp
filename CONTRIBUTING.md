# Contributing to ANPS-TradeMeUp

Thank you for your interest in contributing to ANPS-TradeMeUp! This document provides guidelines and information for contributors.

## How to Contribute

We welcome contributions through:
- **Pull Requests** - Bug fixes, new features, improvements
- **Issues** - Bug reports, feature requests, questions

## Contribution License Agreement

By submitting a pull request or contributing code to this repository, you agree that:

- Your contribution may be used, modified, or relicensed by the maintainer
- You retain no ownership over the submitted code
- All contributions become the exclusive property of the copyright holder (arn-c0de)
- You grant the maintainer full rights to use your contribution in any way

## Development Workflow

1. **Fork the repository** (if you have write access, you can create a branch directly)

2. **Create a branch** for your changes:
   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/your-bug-fix
   ```

3. **Make your changes** following the project's coding standards:
   - Follow PEP 8 style guidelines
   - Use type hints where appropriate
   - Add docstrings for new functions/classes
   - Update relevant documentation

4. **Test your changes**:
   ```bash
   pytest tests/
   ```

5. **Commit your changes** with clear, descriptive commit messages:
   ```bash
   git commit -m "Add: description of your change"
   ```

6. **Push to your fork/branch**:
   ```bash
   git push origin feature/your-feature-name
   ```

7. **Open a Pull Request** with:
   - A clear description of what was changed and why
   - Reference to any related issues
   - Screenshots (if applicable)

## Code Style

- Python 3.11+ syntax
- Follow existing code patterns
- Use type hints (`typing` module)
- Format code with `black` (line length: 100)
- Lint with `ruff`

## Testing

- Write tests for new features
- Ensure all existing tests pass
- Run tests before submitting PR:
  ```bash
  pytest tests/
  ```

## Reporting Issues

When reporting bugs or requesting features:

- Use the GitHub issue tracker
- Provide clear descriptions
- Include steps to reproduce (for bugs)
- Add relevant labels if you have permission

## Questions?

If you have questions about contributing, feel free to:
- Open an issue with the `question` label
- Contact the maintainer: arn-c0de@protonmail.com

---

**Note:** All contributions are subject to the repository's proprietary license. By contributing, you acknowledge that your contributions become the property of the copyright holder.
