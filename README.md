# Linxira Gaming Manager

Linxira Gaming Manager is a user-level library and compatibility workspace for
Linxira OS. It discovers Steam libraries, imports non-Steam executables,
launches games with fixed argument arrays, detects installed compatibility
tools, creates explicit restic backups, and deploys the reviewed gaming
environment through a catalog-bound plan and confirmation.

The setup workflow requests only `bundle-gaming-setup` from the canonical
Catalog. It shows the resulting immutable package plan and uses the same fixed
`linxira-components` confirmation/apply boundary as the other Linxira software
managers. It never invokes a package manager or shell directly.

Imported games use stable IDs, per-game managed prefixes, an environment
allowlist, and a fixed UMU or Wine runner. Only `.exe` payloads are accepted;
launch status and logs remain visible until the process exits.

State is stored in
`${XDG_DATA_HOME:-$HOME/.local/share}/linxira/gaming-manager/state.db`.
Backups use an existing restic repository and password file selected by the
user. Password contents are never stored by Gaming Manager.
