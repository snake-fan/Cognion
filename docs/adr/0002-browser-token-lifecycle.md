# Keep access tokens in memory and refresh tokens in secure cookies

Cognion uses short-lived access JWTs held only in browser memory for authenticated API requests, while longer-lived opaque random refresh tokens are stored in HttpOnly, Secure, SameSite cookies; only their hashes are persisted and each refresh rotates the token. This avoids exposing durable credentials to browser JavaScript while preserving login across page reloads; database-backed refresh sessions support renewal, revocation, multiple devices, and replay detection without pretending refresh credentials are stateless.
