# Deploy the web client and API on the same site

Cognion's production web client and API share one site, with the API exposed below `/api` through a reverse proxy. This permits stricter refresh-cookie settings and avoids a cross-site credential and CSRF model; development origins remain an explicit environment-specific allowlist rather than a wildcard.
