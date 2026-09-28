# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

## [0.1.2] - 2026-09-28

### Removed
- Personal device curves and model-specific “raw FR as target” dumps (kept only shared targets: Harman / diffuse field / LMG / etc.)
- Personal one-off import scripts (`import_fd02` / `import_xlm` / `import_oratory_curves` / bench helpers)
- Hardcoded local paths (`F:\MIMO-Space`, `F:\Hermes-Deepseek`) from docs and tools

### Fixed
- Docs and tests no longer assume personal headphone IDs or `Device: Fiio`
- `curve_store` no longer ships personal built-in device names (import curves yourself)

### Docs
- Deployment guide uses placeholder paths (`path/to/PEQ-WebUI`)

## [0.1.1] - 2026-09-28

### Fixed
- Default APO device scope is now `Device: all` so EQ is not silently ignored on machines without a FiiO-named endpoint
- `is_mounted_fiio` (compat field) accepts `Device: all` and any `Device:` line instead of requiring `Device: Fiio`
- Seed presets use generic examples and `device_scope=all` (no personal headphone IDs)

### Added
- `tools/takeover-admin.ps1` — explicit ConfigPath migration for first-time APO takeover (`install()` alone may skip migrate)

### Docs
- Deployment guide: takeover script path, restart-after-takeover, absolute ConfigPath when moving the project, Device scope pitfall

## [0.1.0] - 2026-09-12

### Added
- Initial public layout: backend, web UI, curve store, fit engines, bilingual README, acknowledgments
