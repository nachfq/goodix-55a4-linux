# Omarchy screen unlock with fingerprint

On 2026-10-14 the owner accepted the initial host trials as sufficient and
declined further biometric test rounds. They selected screen unlocking as the
first everyday integration. The assistant enabled it through normal one-shot
Polkit authorization, reusing the existing host right-index enrollment.

## Exact change

Created `/etc/pam.d/omarchy-lock-fingerprint`, root:root 0644, with the recipe
versioned in [config/pam/omarchy-lock-fingerprint](../config/pam/omarchy-lock-fingerprint):

```text
#%PAM-1.0
auth       required                    pam_fprintd.so
account    include                     system-local-login
```

This matches the fingerprint-specific PAM service in the installed Omarchy
setup command. Only this new file was created; existing files were not replaced.
Creation used an exclusive, no-follow open and refused an existing destination.

Installed Omarchy uses its Quickshell session lock, with independent PAM
contexts for `omarchy-lock-password` and `omarchy-lock-fingerprint`.
`beginLock()` refreshes fingerprint availability, so no shell restart or reboot
was required. Fingerprint success can unlock the screen while password entry
remains independently available. The existing password PAM configuration was
preserved byte-for-byte.

The complete `omarchy setup security fingerprint` wizard was not run: it would
also configure sudo/Polkit and repeat enrollment. Sudo, Polkit, login and SDDM
PAM configurations remain unchanged. No extra packages, sensor key/firmware
operation, image/template inspection, or Git publication occurred.

## Usage

Lock the screen normally, or run:

```sh
omarchy system lock
```

When the reader lights, rest the registered right index on it without pressing
the power button. The existing password field is still available.
No extra lock or biometric trial was launched by the assistant; actual screen
unlock was later reported successful by the owner with both fingerprint and
password (2026-10-14). These are owner observations, not assistant-run trials.
Earlier host CLI results are in
[Test018–020](host-deployment.md).

## Verification and source reference

Read-only checks confirmed exact file content, regular-file/root:root/0644
metadata and unchanged password-lock/sudo/login/Polkit/SDDM PAM baselines.
Only hashes of those existing configurations were retained in ignored local
`work/lock-screen-integration-baseline.json`; no authentication secrets or
biometric data were inspected or published.

Source inspected locally: Omarchy `4.0.4-1`, Quickshell `0.3.1-1`.

| Installed source | SHA-256 |
| --- | --- |
| `/usr/share/omarchy/bin/omarchy-setup-security-fingerprint` | `e645f16dbee117f9e8d667da21d6d66197722a1df9a1730c108e0d325c807d59` |
| `/usr/share/omarchy/shell/plugins/lock/Service.qml` | `3f0a265a09f7957e8f5d74666595d3136ec64899c414426190460f9e2098e701` |

The installed module `/usr/lib/security/pam_fprintd.so` was already present.
Those initial checks established configuration. The owner subsequently reported
successful screen unlock by both methods. See sudo/login integration (covered in a later commit: `sudo-login-integration.md`)
for the separately requested later PAM changes.

## Reversal

To disable only this screen-unlock integration, verify that the installed file
still matches the versioned recipe, then remove that one file:

```sh
cmp config/pam/omarchy-lock-fingerprint /etc/pam.d/omarchy-lock-fingerprint && \
  sudo -- /usr/bin/rm -- /etc/pam.d/omarchy-lock-fingerprint
```

Stop and review a changed file instead of deleting an unrelated configuration.
Do this before removing the [contained driver deployment](host-deployment.md).
Its existing controller owns the driver payload and service override; it does
not remove this separately added PAM file. Fingerprint templates remain intact
when disabling screen unlock, and the password PAM file needs no restoration.
