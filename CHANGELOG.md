# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.1] - 2026-04-17

### Added
- `--version` / `-V` flag: prints the installed version and exits (`ltmsh --version`).

### Fixed
- `__init__.__version__` was incorrectly set to `0.1.0`; now correctly reflects the package version.

## [0.2.0] - 2026-04-15

### Added
- `--scan-from DATE` flag on all query commands to skip journal files older than a given date, improving performance on large vaults.
- All journal files are now scanned by default (not just files within the query period), so CLOCK entries on old tasks are never missed.

### Fixed
- Corrupt or unreadable config files are handled gracefully with a clear error message.
- TOML escaping issues in generated config files.
- Scan buffer widened to 2 days to avoid missing entries near day boundaries.

## [0.1.0] - 2026-04-14

### Added
- Initial release.
- `ltmsh today`, `ltmsh week`, `ltmsh range` commands to query CLOCK entries from LogSeq journal files.
- `ltmsh configure` interactive setup wizard.
- JSON and `--pretty` table output modes.
- `--tag`, `--ref`, `--status` filters with AND/OR logic.
- `--indent`, `--fields`, `--strip-tags`, `--strip-refs` output options.
- TOML config file at `~/.logseq-tmsh/config.toml` with `default_fields`, `scan_from`, and `extra_dirs` support.
