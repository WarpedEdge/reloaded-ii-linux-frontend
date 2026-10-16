# Runtime removal design (not implemented)

Deleting a Proton prefix is not necessary to uninstall a Windows runtime. It is a broader operation that can remove game saves, configuration, launchers, other dependencies and this manager's reset backups. The manager does not delete prefixes.

A future targeted runtime-removal feature should:

1. Before the first dependency installation, inventory both x86/x64 installed packages, exact versions and uninstall identities in the selected prefix. Store a filesystem/registry baseline or full recoverable snapshot, with an explicit storage estimate. A version list alone cannot reverse upgrades of existing components.
2. Run the official installer and retain its logs. Compare before/after state and distinguish newly added components from pre-existing or upgraded components. Do not infer ownership from display names or timestamps alone.
3. Present a specific removal plan. Components that were already present or have uncertain attribution stay installed. Even newly added packages can later become game dependencies; additions are not proof of exclusive Reloaded-II ownership.
4. Use validated official Windows uninstall mechanisms within the same existing Proton environment, without a shell, Linux root access or host package-manager changes. Never delete runtime DLL directories manually or execute arbitrary uninstall strings from registry data. Microsoft documents the .NET Uninstall Tool's supported install methods and limitations; operation through Proton still needs testing. VC++ needs its own supported package-specific uninstall route.
5. Verify exit codes and resulting inventories, retain failure diagnostics, and support recovery. Restoring an entire old prefix snapshot can also rewind later saves/settings; it must be a separate, explicit operation with current user data backed up.

Existing manager installations do not have this baseline, so Reset All currently resets Reloaded-II files/configuration and ASI deployment while retaining Windows runtimes. Current backups cover the manager's own changes, not a pre-install prefix snapshot. A prefix rebuild is a last-resort troubleshooting option, not the normal reset operation; backing up/renaming it is preferable to deleting the only copy, and Steam Cloud must not be assumed to cover every save.

References:

- [Microsoft .NET Uninstall Tool limitations](https://learn.microsoft.com/en-us/dotnet/core/additional-tools/uninstall-tool-overview)
- [Valve Proton FAQ: prefixes and saved games](https://github.com/ValveSoftware/Proton/wiki/Proton-FAQ)
