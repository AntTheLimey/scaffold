# Authentication and Authorization Patterns

## JWT (JSON Web Tokens)

### Structure

A JWT has three parts: header.payload.signature

```json
// Header
{ "alg": "RS256", "typ": "JWT" }

// Payload
{
  "sub": "user-123",
  "iat": 1700000000,
  "exp": 1700003600,
  "roles": ["user"]
}
```

### Security requirements

- **Algorithm**: Use RS256 (asymmetric) or ES256 for public/private key
  signing. Use HS256 only for internal services with a shared secret.
- **Expiration**: Always set `exp`. Access tokens: 15-60 minutes.
  Refresh tokens: 7-30 days.
- **Validation**: Verify signature, expiration, issuer (`iss`), and
  audience (`aud`) on every request.
- **Storage**: Store in HTTP-only, Secure, SameSite cookies. Never in
  localStorage (accessible to XSS).
- **Revocation**: JWTs cannot be revoked after issuance. Use short
  expiration + refresh token rotation, or maintain a token blocklist.

### Common vulnerabilities

- **Algorithm confusion**: Accepting `alg: none` or switching from RS256
  to HS256 with the public key as the secret. Always validate the algorithm
  on the server.
- **Missing expiration check**: A JWT without `exp` or with a very long
  expiration is a persistent credential.
- **Sensitive data in payload**: JWTs are base64-encoded, not encrypted.
  Never put passwords, PII, or secrets in the payload.

## Session Management

### Server-side sessions

```
Client → Session ID (cookie) → Server → Session Store (Redis/DB)
```

- Session IDs: 128+ bits of cryptographically random data.
- Store in HTTP-only, Secure, SameSite=Lax cookies.
- Regenerate session ID after login (prevent session fixation).
- Set idle timeout (30 minutes) and absolute timeout (8 hours).
- Invalidate on logout, password change, and privilege escalation.

### Session storage

- **Redis**: Fast, supports TTL natively. Good for most applications.
- **Database**: Persistent, queryable (list active sessions). Slower
  than Redis.
- **In-memory**: Acceptable for development. Not for production
  (lost on restart, not shared across instances).

### Cookie attributes

```
Set-Cookie: session_id=abc123;
  HttpOnly;           # not accessible via JavaScript
  Secure;             # only sent over HTTPS
  SameSite=Lax;       # prevents CSRF for most cases
  Path=/;
  Max-Age=1800;       # 30 minutes
```

## OAuth 2.0 Flows

### Authorization Code Flow (recommended for web apps)

```
1. App redirects user to authorization server with:
   client_id, redirect_uri, response_type=code, scope, state

2. User authenticates and consents.

3. Authorization server redirects to redirect_uri with:
   code, state

4. App exchanges code for tokens (server-to-server):
   POST /token with code, client_id, client_secret, redirect_uri

5. Authorization server returns:
   access_token, refresh_token, expires_in
```

### Authorization Code Flow with PKCE (for SPAs and mobile)

Same as above, but replaces client_secret with:
- `code_verifier`: Random string (43-128 characters).
- `code_challenge`: SHA256 hash of code_verifier, base64url-encoded.

Step 1 includes `code_challenge`. Step 4 includes `code_verifier`.
The authorization server verifies the hash matches.

### Security requirements

- Always validate `state` parameter to prevent CSRF.
- Use PKCE for all public clients (SPAs, mobile apps).
- Store tokens securely (HTTP-only cookies for web, secure storage for
  mobile).
- Validate redirect URIs exactly (no wildcards, no open redirects).

## Password Hashing

### Recommended algorithms

| Algorithm | Work Factor  | Notes                          |
| --------- | ------------ | ------------------------------ |
| Argon2id  | m=64MB, t=3  | Recommended by OWASP. Memory-hard. |
| bcrypt    | cost=12      | Widely supported. Max 72 bytes input. |
| scrypt    | N=2^15, r=8  | Memory-hard. Less common.      |

### Implementation

```python
# Python with passlib
from passlib.hash import argon2

hashed = argon2.using(memory_cost=65536, time_cost=3).hash(password)
is_valid = argon2.verify(password, hashed)
```

### Rules

- Never store passwords in plaintext or with reversible encryption.
- Never use MD5, SHA1, or SHA256 for passwords (too fast to brute force).
- Never use a global salt. Each password gets a unique random salt
  (handled automatically by bcrypt/argon2).
- Hash on the server, not the client. Client-side hashing does not replace
  server-side hashing.
- Enforce minimum password length (12+ characters). Check against known
  breach databases (HIBP).

## Rate Limiting

### Strategies

- **Fixed window**: N requests per time window (e.g., 100 requests per
  minute). Simple but allows bursts at window boundaries.
- **Sliding window**: Smooths out bursts. Tracks requests in a rolling
  time period.
- **Token bucket**: Allows bursts up to a limit, then enforces a steady
  rate. Good for APIs.

### What to rate limit

| Endpoint        | Limit               | Key            |
| --------------- | -------------------- | -------------- |
| Login           | 5/min                | IP + username  |
| Registration    | 3/hour               | IP             |
| Password reset  | 3/hour               | email          |
| API endpoints   | 100/min              | API key        |
| File upload     | 10/hour              | user ID        |

### Response

Return `429 Too Many Requests` with:
- `Retry-After` header (seconds until the client can retry).
- Clear error message: "Rate limit exceeded. Try again in 60 seconds."

### Implementation

- Use a centralized rate limiter (Redis-based) for distributed systems.
- Apply at the reverse proxy level (nginx, Cloudflare) for DDoS protection.
- Apply at the application level for business rule limiting.
