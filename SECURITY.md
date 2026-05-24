# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| `main` branch | ✅ |

## Reporting a Vulnerability

**Please do NOT open a public GitHub issue for security vulnerabilities.**

If you discover a security issue (e.g. secret leakage, injection vulnerability, privilege escalation), please report it responsibly:

1. Email the maintainer directly (add your contact in your fork).
2. Include a clear description of the vulnerability and steps to reproduce.
3. Allow up to 72 hours for an initial response.

We will acknowledge your report, work on a fix, and credit you in the release notes (unless you prefer to remain anonymous).

## Security Best Practices for Users

- **Never commit `.env`** — it is in `.gitignore` for a reason.
- Rotate all API keys (`GROQ_API_KEY`, `PEXELS_API_KEY`) if you suspect exposure.
- Change your `INSTAGRAM_PASSWORD` immediately if it is ever committed to a repository.
- Use a **residential proxy** (`INSTAGRAM_PROXY`) when deploying to cloud infrastructure.
- Run the Docker container as a non-root user (already enforced by the provided `Dockerfile`).
