# Pull Request

## Summary

<!-- One or two sentences describing what this PR does and why. -->

## Type of change

- [ ] Bug fix (non-breaking change that fixes an issue)
- [ ] New feature (non-breaking change that adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation only
- [ ] Build / tooling / dev experience
- [ ] Refactor (no functional change)
- [ ] Test only

## Checklist — Project hygiene

- [ ] I ran `make verify` (lint + typecheck + test + cov) locally and it passes
- [ ] I ran `make rebrand-verify` and it passes (no IDM-CORE/IDMMORTALITY residuals in code)
- [ ] I updated the relevant documentation in `docs/`
- [ ] If I introduced a new dependency, I verified its license is compatible (see `docs/DEPENDENCIES_AUDIT.md`)
- [ ] If this PR touches AI integrations, I followed `docs/AI_SOVEREIGNTY_POLICY.md` (no exclusive proprietary dependency in core)
- [ ] If this PR introduces a new module, I added the SPDX header (AGPLv3 by default; FSL-1.1-ALv2 for new optional modules)

## Checklist — CLA acceptance

By submitting this PR I confirm:

- [ ] **I have read and accept the Micelia Contributor License Agreement** ([`docs/CLA.md`](../docs/CLA.md)).
- [ ] My contribution is my original work, or I have clearly marked third-party material with its license and verified compatibility.
- [ ] If I am contributing on behalf of an employer, I have included a statement in the description below confirming the employer has reviewed and accepted the CLA.

## Related issues

<!-- Link to issues this PR addresses, e.g. "Closes #42" or "Refs #17". -->

## How was this tested?

<!--
Briefly describe how you verified the change works:
- Manual testing steps
- New automated tests added
- Existing tests that exercise this code path
-->

## Screenshots / output (if applicable)

<!-- Drop screenshots, logs, or terminal output that illustrate the change. -->

## Notes for reviewers

<!-- Anything reviewers should pay special attention to, alternative approaches considered, etc. -->
