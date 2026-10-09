# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-10-09

### Fixed
- Neutralize spreadsheet formulas in exported revalidation CSV cells while preserving stored query text, task reasons, and resolver names.
- Add API regression coverage for formula prefixes, whitespace, and ordinary multiline CSV text.

## [1.0.0] - 2026-10-07

### Added
- Initial release of Knowledge Freshness Monitor.
- Document revision and expiration tracking with chunk-level lexical and semantic drift analysis.
- Citation dependency graph engine calculating direct and transitive impact propagation for RAG answers.
- Revalidation task scheduler with priority scoring, batch scheduling, state tracking, and export workflows.
- Opt-in LLM advisory reports supporting OpenAI-compatible, Anthropic, Gemini, and Ollama endpoints with grounded citations and error redaction.
- OIDC authorization-code authentication with Keycloak, session cookies, CSRF protection, role-based access control (viewer, analyst, admin), and local demo mode.
- Complete React + TypeScript dashboard with citation graph visualization, document management, revalidation queue, and benchmark evaluation suite.
- Docker containerization and compose orchestration with Keycloak realm configuration.
