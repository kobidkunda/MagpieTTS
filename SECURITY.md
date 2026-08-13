# Security Policy

## Design posture

Magpie TTS Server is a **LAN appliance**. By design it has **no authentication**
and binds `0.0.0.0:8092`. It is intended to sit inside an application network
(e.g. alongside a voice-agent backend), never directly exposed to the public
internet.

## Reporting a vulnerability

If you discover a security issue, please report it responsibly by opening a
private advisory on the repository. Do **not** open a public issue for
vulnerabilities.

## What you should do

- Restrict access with a firewall / security group to trusted hosts only.
- Do not expose `:8092` to the internet.
- Treat the GUI as an administrative console (it can switch models and run
  benchmarks) — limit who can reach it.
- The server never validates `Authorization` headers; clients may send any API
  key. Do not rely on the API key for access control.

## What we will not accept as vulnerabilities

- Missing authentication — this is an explicit, documented design decision.
- Missing TLS — terminate TLS at a reverse proxy if you need it.
- Requests to bind `0.0.0.0` — again by design.

## Supported versions

Only the latest commit on the default branch is supported.
