# Security Checklist (OWASP Top 10)

## A01: Broken Access Control

Check every endpoint and data access path:

- **Missing authorization checks**: Does the endpoint verify the user has
  permission to access this specific resource? Checking authentication (who
  you are) is not the same as authorization (what you can do).
- **Insecure Direct Object Reference (IDOR)**: Can a user access another
  user's data by changing an ID in the URL? `GET /api/users/123/data` — does
  it verify user 123 is the authenticated user?
- **Path traversal**: Can file paths be manipulated? Any user input used in
  file operations must be sanitized and constrained to an allowed directory.
- **CORS misconfiguration**: Is `Access-Control-Allow-Origin` set to `*` on
  authenticated endpoints? It should be restricted to known origins.
- **Missing function-level access control**: Are admin endpoints protected?
  Hiding the URL is not security.

## A02: Cryptographic Failures

- **Sensitive data in plaintext**: Passwords, tokens, PII in logs, error
  messages, or database fields without encryption.
- **Weak hashing**: MD5 or SHA1 for passwords. Use bcrypt, scrypt, or Argon2.
- **Hardcoded secrets**: API keys, database passwords, or encryption keys in
  source code. Use environment variables or a secrets manager.
- **Missing TLS**: Any HTTP endpoint that handles authentication or sensitive
  data must use HTTPS.
- **Weak random generation**: Using `Math.random()`, `random.random()`, or
  similar for tokens, session IDs, or cryptographic purposes. Use
  cryptographically secure generators.

## A03: Injection

- **SQL injection**: Any SQL query built with string concatenation or
  interpolation of user input. Use parameterized queries always.
- **NoSQL injection**: Passing unsanitized objects to MongoDB queries
  (`{$gt: ""}` as a password field).
- **Command injection**: Passing user input to `exec`, `system`, `subprocess`
  without sanitization. Avoid shell commands; use library APIs.
- **XSS (Cross-Site Scripting)**: User input rendered in HTML without
  escaping. Use framework auto-escaping. Be cautious with `innerHTML`,
  `dangerouslySetInnerHTML`, or template `{{{ }}}` syntax.
- **Template injection**: User input in server-side template expressions.
- **LDAP injection**: User input in LDAP queries without escaping.

## A04: Insecure Design

- **Missing rate limiting**: Login endpoints, API endpoints, and form
  submissions without throttling. Enables brute force and DoS.
- **Missing input validation**: Accepting any input shape without checking
  type, length, range, and format.
- **Trust boundary violations**: Treating client-side validation as sufficient.
  All validation must be repeated server-side.
- **Missing business logic validation**: Applying a discount twice, ordering
  negative quantities, transferring negative amounts.

## A05: Security Misconfiguration

- **Default credentials**: Using default admin passwords, API keys, or
  database credentials.
- **Unnecessary features enabled**: Debug mode, verbose error messages,
  directory listing in production.
- **Missing security headers**: Content-Security-Policy, X-Content-Type-Options,
  X-Frame-Options, Strict-Transport-Security.
- **Overly permissive permissions**: File permissions, database user privileges,
  cloud IAM roles broader than needed.

## A06: Vulnerable Components

- **Outdated dependencies**: Known CVEs in third-party libraries. Check
  dependency versions against vulnerability databases.
- **Unused dependencies**: Every dependency is an attack surface. Remove
  unused packages.
- **Unverified sources**: Dependencies from untrusted registries or
  unverified publishers.

## A07: Authentication Failures

- **Credential stuffing**: No rate limiting on login attempts. No account
  lockout after repeated failures.
- **Weak password policies**: No minimum length, no complexity requirements.
- **Session fixation**: Session ID not regenerated after login.
- **Token exposure**: JWT or session tokens in URL parameters, referrer
  headers, or logs.
- **Missing logout**: No session invalidation endpoint, or client-side-only
  logout that does not invalidate the server session.

## A08: Data Integrity Failures

- **Deserialization of untrusted data**: Using pickle, Java serialization,
  or similar with user-provided data.
- **Missing integrity checks**: Downloading code or data without verifying
  checksums or signatures.
- **CI/CD pipeline vulnerabilities**: Build scripts that pull unverified
  dependencies or execute untrusted code.

## A09: Logging and Monitoring Failures

- **Sensitive data in logs**: Passwords, tokens, PII, credit card numbers
  logged in plaintext.
- **Missing audit trail**: Security-relevant events (login, access denied,
  data modification) not logged.
- **No alerting**: Log data exists but no one monitors it for anomalies.

## A10: Server-Side Request Forgery (SSRF)

- **Unvalidated URLs**: User-provided URLs used in server-side HTTP requests
  without validation. Can access internal services, cloud metadata endpoints.
- **DNS rebinding**: Validating the URL hostname at parse time but not at
  request time. The DNS record can change between validation and request.
- **Allow-list bypass**: URL validation that can be bypassed with URL encoding,
  IPv6, or redirect chains.
