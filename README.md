# Newsletter Engine

Self-hosted newsletter generator and sender (Gmail API). No Docker required.

## Quick start

1. Create a venv and install dependencies.
2. Copy `.env.example` to `.env` and edit values.
3. Edit `config/*.json` to define groups, sources, templates, newsletters.
4. Initialize DB by running any CLI command; tables auto-create.

## CLI

- `python -m src.cli poll-sources`
- `python -m src.cli build-newsletter --newsletter-id <id> [--dry-run]`
- `python -m src.cli send-run --run-id <id>`
- `python -m src.cli run-scheduler`
- `python -m src.cli prune`
- `python -m src.cli report --newsletter-id <id> --days 30`

## Services

- Tracking web service: `python -m src.app`
- Scheduler: `python -m src.cli run-scheduler`

Systemd unit files and logrotate config are in `system/`.
