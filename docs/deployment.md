# Deployment

Geo-Pulse currently supports a single-process Python 3.11+ deployment with local filesystem storage. Install the package, provide configuration under `configs/`, and start the API through the installed CLI.

Generated datasets, models, maps, reports, and run metadata should be placed on durable storage in a hosted environment. Restrict artifact access when property records contain sensitive information.

Production hardening should add authentication, a durable job queue, object storage, structured telemetry, request limits, external-secret management, retention policies, backups, and a release rollback procedure.
