# Security Policy

## Supported Versions

We actively support security updates for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability in ANPS-TradeMeUp, please report it responsibly. **Do not open a public issue.**

### How to Report

1. **Email**: Send details to `arn-c0de@protonmail.com`
2. **GitHub Security Advisories**: Use the [Security Advisories](https://github.com/arn-c0de/ANPS-TradeMeUp/security/advisories) feature

### What to Include

Please include the following information in your report:

- **Description**: Clear description of the vulnerability
- **Steps to Reproduce**: Detailed steps to reproduce the issue
- **Affected Versions**: Which versions are affected
- **Potential Impact**: Assessment of potential impact (data exposure, system compromise, etc.)
- **Suggested Fix**: If you have ideas for a fix, please include them

### Response Timeline

- **Acknowledgment**: Within 3 business days
- **Initial Assessment**: Within 7 business days
- **Fix Timeline**: Depends on severity and complexity

### Security Best Practices

When using ANPS-TradeMeUp:

1. **API Keys**: Never commit API keys or credentials to version control
   - Use `.env.local` for local development (already in `.gitignore`)
   - Use environment variables or secure secret management in production

2. **Database Security**: 
   - Use strong database credentials in production
   - Enable encryption for database connections when possible
   - Regularly backup your database

3. **Network Security**:
   - Run the API behind a reverse proxy (nginx, Traefik) in production
   - Use HTTPS/TLS for all external connections
   - Restrict CORS origins appropriately

4. **Dependencies**:
   - Regularly update dependencies: `poetry update` or `pip install --upgrade`
   - Review security advisories for dependencies

5. **Access Control**:
   - Limit access to the dashboard and API endpoints
   - Use authentication/authorization for production deployments
   - Review and restrict file system permissions

### Known Security Considerations

- The application uses environment variables for sensitive configuration
- Database files may contain sensitive financial data - ensure proper access controls
- LLM API keys should be rotated regularly
- The dashboard runs on localhost by default - ensure proper network configuration in production

### Security Updates

Security updates will be released as patch versions (e.g., 1.0.3 → 1.0.4) and will be documented in:
- GitHub Releases
- Security Advisories (for critical issues)
- CHANGELOG.md (if maintained)

---

**Thank you for helping keep ANPS-TradeMeUp secure.**
