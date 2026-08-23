---
description: Commit pending changes, push, open a PR, and monitor it for review feedback
---

Ship the current branch's pending work end-to-end. Work through these steps
in order and don't skip any:

1. **Check for a clean base.** `git status` to see what's staged, unstaged,
   and untracked. If anything looks like a stray local file or secret
   (`.env`, credentials, keys), stop and ask before touching it — don't
   stage it blindly with a broad `git add -A`.

2. **Run CI locally.** `./scripts/ci-check.sh` — it runs the same steps as
   `.github/workflows/ci.yml` (shellcheck, backend/cli ruff+pytest, frontend
   lint/format/check/vitest/playwright e2e). If it fails, fix the underlying
   issue and rerun; don't push on red.

3. **Stage and commit.** `git add` the relevant files. Write a commit
   message that explains *why*, not a restated diff — see CONTRIBUTING.md's
   "Commits / PRs" section. If the pending changes are several unrelated
   features, prefer one self-contained commit per feature over one giant
   commit, unless the user has asked for everything bundled together.

4. **Push.** Push the current branch to `origin` (`-u` if it has no
   upstream yet).

5. **Open the PR.** `gh pr create --base main` with a title and body
   summarizing the change and any manual verification performed (per
   CONTRIBUTING.md, since plugin UI rendering isn't covered by the backend
   suite). Report the PR URL back to the user.

6. **Monitor for feedback.** Poll the PR periodically (`gh pr view --json
   reviews,comments,statusCheckRollup`, or `gh pr checks`) for new review
   comments, requested changes, or failing checks. When feedback comes in:
   read it, make the corresponding code changes, run `./scripts/ci-check.sh`
   again, commit, and push a follow-up commit to the same branch — don't
   force-push over review history. Keep watching (space out polls a few
   minutes apart; no need to busy-loop) until the PR is approved/merged, or
   the user says to stop.

$ARGUMENTS
