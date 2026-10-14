# Fingerprint for sudo and graphical login

On 2026-10-14 the owner reported that screen unlock worked with both fingerprint
and password, then requested sudo and login integration. The assistant configured
sudo and the active graphical login manager, SDDM, with normal one-shot Polkit
authorization. The existing host enrollment was reused.

## Exact changes

Inserted the versioned [fingerprint prefix](../config/pam/fingerprint-auth-prefix.conf)
immediately after the existing header in `/etc/pam.d/sudo` and `/etc/pam.d/sddm`:

```text
# BEGIN thinkpad-fingerprint
auth      [success=1 default=ignore] pam_exec.so quiet /usr/bin/omarchy-hw-laptop-closed
auth      sufficient pam_fprintd.so max-tries=1 timeout=10
# END thinkpad-fingerprint
```

The closed-lid gate follows the installed Omarchy integration: success skips
exactly the next fingerprint module, so the existing password stack runs.
With the lid open, fingerprint success satisfies authentication; a failure or
timeout continues into the original authentication rules. Account/session checks
remain in their original files. Fingerprint gets one attempt and a10-second
timeout; debug is not enabled. These options and serialized PAM behavior were
verified against the installed `pam_fprintd(8)` manual.

The original remainder of both files is byte-identical, with original modes
and root:root ownership retained. Shared `system-auth` was not edited. Screen
password/fingerprint PAM, console `/etc/pam.d/login`, Polkit, SDDM autologin PAM
and autologin settings remain unchanged. No packages, extra enrollment,
key/firmware operations, image/template inspection or Git publication.

## Use

For sudo, the next uncached authorization can use the registered finger.
To request a fresh authorization intentionally:

```sh
sudo -k
sudo -v
```

Touch when the reader lights. If fingerprint fails or times out, the password
path remains available. Closed-lid operation skips fingerprint. Unlike Omarchy's
independent lock contexts, sudo's authentication is sequential.

For the installed SDDM theme, Enter submits login even with an empty password;
the inspected `Main.qml` calls `sddm.login` without a nonempty-password guard.
Submit and touch the registered finger. If that fails, enter the password and
submit again; the fingerprint-first timeout may still precede password checking.
Do not restart SDDM or log out an active work session merely to validate setup.

**Startup disk decryption is separate.** Read-only block ancestry confirmed the
root filesystem lies beneath an encrypted volume. SDDM autologin is configured;
the owner could not confidently identify the startup password screen. A themed
prompt can belong to disk decryption rather than session login. This delivery
does not change the encrypted disk, initramfs, TPM, bootloader or autologin.
Disk unlock uses its own mechanisms, described in the official
[systemd crypttab documentation](https://www.freedesktop.org/software/systemd/man/250/crypttab.html).
The existing startup disk password remains applicable; PAM fingerprint setup
does not substitute for it.

## Checks and limits

Before mutation, both originals had no fingerprint module and matched pinned
hashes. They were backed up privately before replacement. Each replacement used
a fully written/fsynced temporary file followed by an atomic rename; ordinary
failure restores already changed targets. A power loss can leave one file
updated; the saved originals and restoration helper remain available.

Post-install checks confirmed exact expected hashes/modes/ownership of sudo and
SDDM, private backup-directory ownership/mode, and unchanged password-lock,
fingerprint-lock, console-login, Polkit and autologin baselines. Restoration
helper syntax and its non-mutating default mode passed. No live sudo/login PAM
authentication was observed or imposed, no session restart and no further
biometric test round. Configuration is enabled; everyday results remain to be
reported by the owner.

## One-command reversal

Original files and hashes are saved in root-owned0700
`/etc/thinkpad-fingerprint-auth/`. Its sudo/SDDM originals, manifest and standalone
`restore.py` are root-owned0600. The helper is versioned as
[25-restore-pam-auth.py](../scripts/25-restore-pam-auth.py).

To restore only these sudo/SDDM integrations:

```sh
sudo -- /usr/bin/python3 /etc/thinkpad-fingerprint-auth/restore.py --remove
```

The helper accepts only the two known targets, validates saved hashes and refuses
an active configuration changed after this installation. It restores both
originals and deletes only the expected backup namespace. Before backup cleanup
begins, an interrupted restore can be retried while each file still matches its
known before/after hash and all backup entries remain intact. If interrupted
during backup deletion, PAM files are already restored but leftover cleanup
requires inspection; the exact-entry guard refuses an incomplete backup tree.
Screen unlock and templates are preserved. If sudo cannot authorize, normal Polkit
elevation can run this same helper with `pkexec`.

Restore sudo/SDDM and disable the separate lock integration **before** removing
the [contained driver](host-deployment.md). The existing driver controller does
not own the separately added PAM integrations or backup namespace.
