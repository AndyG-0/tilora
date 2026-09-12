# Security Policy

## Supported versions

Tilora ships rolling releases rather than maintained LTS branches — only the
latest release is supported with security fixes. Please update to the latest
version (see the in-app update notification, or `git pull` / `tilora update`)
before reporting an issue.

## Reporting a vulnerability

Please report security vulnerabilities privately using GitHub's
[private vulnerability reporting](https://github.com/AndyG-0/tilora/security/advisories/new)
(the "Report a vulnerability" button under this repo's Security tab), rather
than opening a public issue. This lets us assess and fix the issue before
details are public.

Include as much detail as you can: the affected component (backend, frontend,
CLI, a specific plugin), a reproduction, and the impact you'd expect. We'll
acknowledge reports and follow up as we investigate.

## Scope notes

Tilora is a self-hosted home server that can store third-party AI provider
keys and OAuth client credentials, and is often exposed on a local home
network. See the README's
["Network exposure & security"](README.md#network-exposure--security) section
for the deployment-level security model (what's exposed, how credentials are
handled) — issues in that model are in scope for reports here.
