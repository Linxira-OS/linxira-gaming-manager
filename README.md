# Linxira Gaming Manager

Linxira Gaming Manager is a user-level library and compatibility workspace for
Linxira OS. It discovers Steam libraries, imports non-Steam executables,
launches games with fixed argument arrays, detects installed compatibility
tools, and creates explicit restic backups.

Package Center owns Steam, Lutris, Heroic, and Bottles installation. Component
Manager owns Wine, UMU, Vulkan, GameMode, Gamescope, and related system
foundations. Gaming Manager never invokes pacman, Flatpak, Polkit, sudo, or a
root helper.

State is stored in
`${XDG_DATA_HOME:-$HOME/.local/share}/linxira/gaming-manager/state.db`.
Backups use an existing restic repository and password file selected by the
user. Password contents are never stored by Gaming Manager.
