# Runtime removal (not implemented)

Reset All keeps Windows runtimes. Deleting a Proton prefix is a much broader action: it can remove saves, settings, launchers, other dependencies and this manager's reset backups. The manager never deletes prefixes.

Removing runtimes safely would require records from before the first installation. Existing setups do not have those records, so the manager cannot tell which VC++ or .NET components it added or upgraded.

## What a future implementation needs

1. Record installed x86 and x64 packages, exact versions and uninstall identifiers before setup. Keep a recoverable file and registry backup, with an estimate of its disk space. A version list alone cannot undo an upgrade.
2. Run the official installer and keep its logs. Compare the result with the earlier records. Do not decide which components were added from display names or timestamps alone.
3. Show the user exactly what would be removed. Keep components that were already present or whose origin is unclear. A component installed during setup might also be needed by the game later.
4. Use the official Windows uninstall method in the same Proton environment. Do not delete runtime DLL folders or run arbitrary uninstall commands read from the registry. The .NET Uninstall Tool has limits on supported installations; VC++ needs its own uninstall method. Both need testing through Proton.
5. Check the result, keep failure logs and allow recovery. Restoring a whole prefix backup can rewind newer saves and settings, so that must be a separate action with current user data backed up first.

Current file backups only cover changes made by the manager. They cannot restore the prefix to its state before the Windows runtime installer ran. Rebuilding a prefix should remain a last-resort troubleshooting action. Keep a recoverable copy first; Steam Cloud may not contain every save.

## References

- [Microsoft .NET Uninstall Tool limitations](https://learn.microsoft.com/en-us/dotnet/core/additional-tools/uninstall-tool-overview)
- [Valve Proton FAQ: prefixes and saved games](https://github.com/ValveSoftware/Proton/wiki/Proton-FAQ)
