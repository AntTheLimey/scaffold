# OWASP Top 10 Detection and Remediation

## A01: Broken Access Control

### Detection patterns

- Missing authorization checks after authentication:
  ```python
  # VULNERABLE: authenticates but does not authorize
  @app.get("/users/{user_id}/data")
  def get_data(user_id: int, current_user: User = Depends(get_current_user)):
      return db.query(Data).filter(Data.user_id == user_id).all()
  ```

- IDOR (Insecure Direct Object Reference): User-supplied IDs used without
  ownership verification.

- Path traversal: `../` in file paths not sanitized.

### Remediation

```python
# FIXED: verifies the authenticated user owns the resource
@app.get("/users/{user_id}/data")
def get_data(user_id: int, current_user: User = Depends(get_current_user)):
    if user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(403, "Forbidden")
    return db.query(Data).filter(Data.user_id == user_id).all()
```

- Check ownership on every data access, not just at the route level.
- Use allowlists for file paths. Resolve paths and verify they stay within
  the allowed directory.

## A02: Cryptographic Failures

### Detection patterns

- Passwords stored with MD5, SHA1, or SHA256 (fast hashes, not password hashes).
- Secrets in source code: `API_KEY = "sk-..."`.
- Sensitive data in logs: `logger.info(f"User login: {email}, password: {password}")`.
- Missing TLS on endpoints handling credentials.

### Remediation

- Passwords: bcrypt, scrypt, or Argon2id with appropriate work factors.
- Secrets: Environment variables or a secrets manager (Vault, AWS Secrets Manager).
- Logging: Scrub sensitive fields before logging. Use structured logging
  with an explicit allowlist of loggable fields.
- TLS: Enforce HTTPS in production. Set HSTS headers.

## A03: Injection

### Detection patterns

```python
# SQL INJECTION: string formatting in queries
cursor.execute(f"SELECT * FROM users WHERE email = '{email}'")

# COMMAND INJECTION: user input in shell commands
os.system(f"convert {filename} output.png")

# XSS: unescaped user input in HTML
return f"<p>Welcome, {username}</p>"
```

### Remediation

```python
# Parameterized query
cursor.execute("SELECT * FROM users WHERE email = %s", (email,))

# Library API instead of shell
from PIL import Image
img = Image.open(filename)

# Template with auto-escaping (Jinja2, React, etc.)
# React auto-escapes by default. Avoid dangerouslySetInnerHTML.
```

## A04: Insecure Design

### Detection patterns

- No rate limiting on login, registration, or password reset endpoints.
- Missing input validation: accepting any shape of data without checking
  type, length, or format.
- Client-side-only validation (server trusts client data).
- Business logic flaws: negative quantities, applying coupons multiple times.

### Remediation

- Rate limit authentication endpoints: 5 attempts per minute per IP/account.
- Validate all input server-side using a schema validation library
  (Pydantic, Zod, joi).
- Implement business rule validation in the service layer, not the UI.

## A05: Security Misconfiguration

### Detection patterns

- Debug mode in production: `DEBUG=True`, `NODE_ENV=development`.
- Default credentials: admin/admin, root/root.
- Verbose error messages exposing stack traces to users.
- Missing security headers.
- Directory listing enabled on web servers.

### Remediation

- Environment-specific configuration. Never use the same config for dev
  and production.
- Security headers: CSP, X-Content-Type-Options, X-Frame-Options, HSTS.
- Generic error messages for users. Detailed errors in server logs only.

## A06: Vulnerable Components

### Detection patterns

- Run dependency audit tools:
  - `npm audit` / `yarn audit`
  - `pip-audit` / `safety check`
  - `govulncheck`
  - `cargo audit`
- Check for dependencies that are unmaintained (no updates in 2+ years).
- Check for dependencies pulled from untrusted sources.

### Remediation

- Update dependencies with known CVEs.
- Remove unused dependencies.
- Pin dependency versions in lock files.
- Set up automated dependency scanning in CI (Dependabot, Snyk, Trivy).

## A07: Authentication Failures

### Detection patterns

- No rate limiting on login endpoints.
- Session IDs in URL parameters or referrer headers.
- Weak password requirements (no minimum length, no complexity).
- Sessions not invalidated on logout or password change.
- Missing MFA on sensitive operations.

### Remediation

- Rate limit login: 5 attempts per minute, exponential backoff.
- Session IDs in HTTP-only, Secure, SameSite cookies only.
- Minimum password length: 12 characters. Check against breach databases
  (HIBP API).
- Regenerate session ID after login. Invalidate all sessions on password
  change.

## A08: Data Integrity Failures

### Detection patterns

- Deserializing untrusted data: `pickle.loads(user_input)`,
  `yaml.load(data)` (without SafeLoader).
- CI/CD pipelines downloading unverified dependencies.
- Missing integrity checks on file uploads or downloads.

### Remediation

- Never deserialize untrusted data with unsafe deserializers.
  Use `yaml.safe_load()`, `json.loads()`.
- Verify checksums for downloaded artifacts.
- Pin CI/CD action versions by SHA, not tag.

## A09: Logging and Monitoring Failures

### Detection patterns

- Security events not logged (login attempts, access denied, data changes).
- Sensitive data in logs (passwords, tokens, PII).
- No centralized log collection or alerting.

### Remediation

- Log: authentication events, authorization failures, input validation
  failures, server errors.
- Scrub: passwords, tokens, credit card numbers before logging.
- Alert on: repeated auth failures, unusual access patterns, error spikes.

## A10: Server-Side Request Forgery (SSRF)

### Detection patterns

```python
# VULNERABLE: user-controlled URL in server-side request
url = request.args.get("url")
response = requests.get(url)  # can access internal services
```

### Remediation

- Validate URLs against an allowlist of domains.
- Block internal IP ranges (127.0.0.0/8, 10.0.0.0/8, 169.254.169.254).
- Use a URL parser to resolve the hostname before making the request.
- Do not follow redirects blindly — validate the redirect target.
