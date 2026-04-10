# CLAUDE.md

This file provides guidance to AI assistants (like Claude Code) working with this repository.

## Repository Overview

**Claude-test** is a test/template repository owned by `endyphysio11`. It is currently in a nascent state, containing minimal content and serving as a sandbox for testing Claude AI assistant workflows — in particular, workflows around codebase documentation and AI-driven development.

- **Repository:** `endyphysio11/Claude-test`
- **Remote:** hosted via a local proxy (not a direct GitHub remote)
- **Default branch:** `main`
- **Current state:** Minimal — only a `README.md` exists in the tracked file tree

## Repository Structure

```
Claude-test/
├── .git/           # Git metadata (not tracked)
├── README.md       # Project title placeholder
└── CLAUDE.md       # This file — AI assistant guide
```

No source code, dependencies, build system, tests, or CI/CD pipelines exist yet. As the project grows, this file should be updated to reflect the actual structure.

## Git Workflow

### Branching Convention

Feature branches follow this naming pattern:

```
claude/<short-description>-<random-id>
```

Example: `claude/add-claude-documentation-RiRFQ`

Always develop on the branch specified for your task. Never push directly to `main` without explicit permission.

### Standard Git Operations

**Cloning / switching branches:**
```bash
git fetch origin <branch-name>
git checkout <branch-name>
```

**Committing changes:**
```bash
git add <specific-files>        # Stage specific files — avoid git add -A or git add .
git commit -m "descriptive message"
```

**Pushing changes:**
```bash
git push -u origin <branch-name>
```

If a push fails due to a network error, retry up to 4 times with exponential backoff (2s, 4s, 8s, 16s).

### Commit Message Style

- Use the imperative mood: "Add", "Fix", "Update", "Remove"
- Keep the subject line concise (under 72 characters)
- Focus on the *why*, not just the *what*
- Do not amend published commits — create new commits instead

## Development Conventions

Since no source code exists yet, the following conventions should be adopted as the repository grows:

### General Principles

- Prefer editing existing files over creating new ones
- Do not add features, refactoring, or "improvements" beyond what is explicitly requested
- Do not add speculative abstractions or future-proofing
- Only add comments where the logic is not self-evident
- Avoid backwards-compatibility hacks for unused code — delete it cleanly

### Security

- Never introduce command injection, XSS, SQL injection, or other OWASP Top 10 vulnerabilities
- Only validate input at system boundaries (user input, external APIs)
- Do not commit secrets, credentials, or `.env` files

### File Creation

- Do not create documentation files (e.g., `*.md`, `README`) unless explicitly asked
- Do not create helper utilities or abstractions for one-time operations

## Pull Requests

Do not create a pull request unless the user explicitly asks for one. When creating a PR, use the format:

```
## Summary
- <bullet points>

## Test plan
- [ ] <checklist items>
```

## Updating This File

Whenever the repository gains new structure — source code, dependencies, tests, CI, build scripts — update this `CLAUDE.md` to reflect:

1. Revised directory structure
2. How to install dependencies
3. How to build/run the project
4. How to run tests
5. Any new conventions or tooling configurations
