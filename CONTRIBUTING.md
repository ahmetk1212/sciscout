# Contributing to SciScout

Thanks for your interest in contributing! 🚀

## 1) Fork & Branch

1. Fork this repository
2. Create a feature branch from default branch:

```bash
git checkout -b feat/short-description
```

## 2) Commit format (Conventional Commits)

Please use one of:

- `feat: ...`
- `fix: ...`
- `docs: ...`
- `refactor: ...`

Examples:

- `feat: add europe pmc source adapter`
- `fix: handle empty citation list in synthesizer`
- `docs: improve quickstart and API examples`

## 3) Code style

- Linter: `ruff`
- Max line length: `100`

Run before pushing:

```bash
ruff check .
```

## 4) Testing expectations

- Add or update tests for non-trivial changes when possible.
- If no tests exist for your area, include at least a smoke validation and explain manual test steps in PR description.

## 5) Open a Pull Request

1. Push your branch
2. Open PR with:
   - clear summary
   - motivation/context
   - screenshots/logs if relevant
   - checklist of what you tested

## 6) Review process

- Keep PRs focused and small when possible.
- Address review comments with follow-up commits.
- Be respectful and collaborative in discussions.

Thanks for helping improve SciScout 💡
