# Working instructions

This project investigates Goodix USB 27c6:55a4 on a ThinkPad E14 Gen 2.
The owner wants to learn step by step. Keep repository content, filenames,
commit messages, and GitHub metadata in English. Continue explaining progress
to the owner in Spanish unless asked otherwise.

- The owner wants to run and understand experiments personally. Prepare small,
  readable scripts and explain one experiment at a time. Leave hardware and
  detection runs to the owner unless explicitly delegated; wait for their output
  before proceeding to the next experiment. Offline syntax and source checks are
  allowed. Do not silently run the experiment while preparing it.

- Before downloading additional sources, installing packages, or making persistent
  sensor changes, explain the exact operations and agree on their scope with the
  owner. Do not infer authorization for future stages from an earlier approval.
  Honor explicit authorizations already given in the conversation.
- The owner completed the bounded firmware/key-state probe, one known-key write
  and one standalone 108 x 88 sensor image; see docs/first-capture-test.md.
  The owner subsequently completed standalone enrollment and reported match,
  non-match and a satisfactory pilot; see docs/private-verification.md.
  Contained fprintd preparation passed offline checks, and the owner reported
  successful hardware detection/private teardown and completing native enrollment.
  The persisted native template/manifest passed host-only checks; the owner then
  reported one declared-same native MATCH and one declared-other native NO_MATCH.
  The initial contained native recognition experiment is complete. Agree on a
  bounded next delivery before host installation/service/authentication changes.
  The owner accepted preparing D14's contained host bundle and guarded
  installation/removal scripts. After D14 review, the owner separately authorized
  installation and normal-host detection (2026-10-14, "hagamoslo"). The assistant
  installed the frozen payload through one-shot Polkit and observed fprintd-list
  expose one reader (Test017). A separately accepted normal-host enrollment
  completed with 16 accepted scans and right-index-finger listed (Test018);
  an earlier unknown-error attempt is inconclusive. One normal-host declared-
  same verification then reported verify-match/exit0 (Test019), after an
  inconclusive error with owner-reported delayed finger placement. The next
  separately accepted declared-other trial reported verify-no-match/exit1
  (Test020). This is normal-CLI behavior; NO_MATCH can mask internal errors and
  lacks the private observer guarantee. The owner accepted the results and
  explicitly declined further biometric test rounds. They selected screen
  unlock: /etc/pam.d/omarchy-lock-fingerprint is now configured using the stock
  recipe, with password unlock unchanged. See docs/lock-screen-integration.md.
  The owner reported successful screen unlock with fingerprint and password,
  then explicitly requested sudo/login. Sudo and SDDM PAM are now configured
  with fingerprint-first/password fallback and private originals/restore helper.
  See docs/sudo-login-integration.md. No live sudo/login result yet. Autologin,
  disk encryption and console login unchanged; Polkit remains separately scoped.
  Do not impose another biometric test round.
  See docs/host-deployment.md.
  See docs/private-fprintd.md. This remains partial evidence, not authentication
  certification.
  Do not run community installers or provisioning utilities. Further PAM,
  sudo, lock or service changes require agreed scope. A device
  listing may activate the installed fprintd through D-Bus; document that effect.
- Distinguish local observations, third-party claims, and hypotheses. Link findings
  to a commit and file. Do not present a partial review as a complete audit.
- Do not publish fingerprint images, templates, dumps, USB captures, secrets, or
  unreviewed logs. Use ignored local paths for experimental data.
- Preserve attribution and review licenses before incorporating third-party code.
- Separate downloading, building, USB access, provisioning, and installation into
  reviewable steps. Count errors and timeouts as inconclusive trials, not correct
  biometric rejections.
- Read README.md and docs/ before proposing changes. Keep documentation consistent
  with the actual state; never mark future tests as completed.
