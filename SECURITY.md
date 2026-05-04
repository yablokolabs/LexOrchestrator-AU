# Security Policy

LexOrchestrator-AU is beta-oriented legal AI infrastructure. Do not deploy it with client data until authentication, tenant isolation, audit logging, secret management, and legal-data licensing have been reviewed for your environment.

## Reporting issues

Please report security issues privately to the repository owner. Do not open public issues containing secrets, exploit details, or client material.

## Deployment checklist

- Set `LEX_API_KEYS` and put the app behind TLS and a trusted reverse proxy.
- Restrict `CORS_ORIGINS`; do not use wildcard origins for firm portals.
- Use managed PostgreSQL backups, encryption, and network restrictions.
- Keep model-provider data-retention settings aligned with client engagement terms.
- Treat `/metrics` as internal; it is API-key protected when `LEX_API_KEYS` is configured.
