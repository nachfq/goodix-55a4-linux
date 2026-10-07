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
- The current stage is auditing and baseline detection using installed software.
  Do not run community installers or provisioning utilities. Do not change PAM,
  sudo, screen locking, or service configuration as part of this stage. A device
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
