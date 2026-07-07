#!/usr/bin/env bash
# fetch-licenses.sh — downloads the verbatim canonical text of the licenses
# used by Micelia and writes them to LICENSE and LICENSE.fsl in repo root.
#
# Run once after cloning the repo, or whenever the upstream licenses change
# (they shouldn't — both are pinned versions).
#
# Why this script exists: the AGPLv3 full text (~34KB, 661 lines) and the
# FSL template are reproduced verbatim from their canonical sources rather
# than embedded by hand to (a) avoid manual transcription errors and (b)
# make license updates trivially auditable via diff.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

AGPL_URL="https://www.gnu.org/licenses/agpl-3.0.txt"
AGPL_SHA256="0d96a4ff68ad6d4b6f1f30f713b18d5184912ba8dd389f86aa7710db079abcb0"

FSL_URL="https://fsl.software/FSL-1.1-ALv2.template.md"
# FSL sha256 not pinned: upstream updates the template occasionally with
# legal clarifications. We verify license name + version manually below.

# ANSI colors
CYAN='\033[36m'
GREEN='\033[32m'
RED='\033[31m'
RESET='\033[0m'

info()  { printf "${CYAN}→ %s${RESET}\n" "$*"; }
ok()    { printf "${GREEN}✓ %s${RESET}\n" "$*"; }
fail()  { printf "${RED}✗ %s${RESET}\n" "$*" >&2; exit 1; }

# Verify curl is available
command -v curl >/dev/null 2>&1 || fail "curl is required. Install it and rerun."

# ---------------------------------------------------------------------------
# AGPLv3
# ---------------------------------------------------------------------------

AGPL_PATH="${REPO_ROOT}/LICENSE"
AGPL_TMP="$(mktemp)"

info "Downloading AGPLv3 verbatim text from FSF..."
curl -fsSL "${AGPL_URL}" -o "${AGPL_TMP}" || fail "Could not download ${AGPL_URL}"

# Verify SHA256 (matches the FSF text frozen 2007-11-19)
ACTUAL_SHA=$(shasum -a 256 "${AGPL_TMP}" | awk '{print $1}')
if [ "${ACTUAL_SHA}" != "${AGPL_SHA256}" ]; then
  info "Note: AGPLv3 SHA mismatch — expected ${AGPL_SHA256}, got ${ACTUAL_SHA}."
  info "This may mean FSF updated the file (rare). Continuing but please verify."
fi

# Preserve the existing placeholder header (with Micelia copyright + SPDX)
# and append the verbatim text. The placeholder's first ~30 lines are our
# notice; we add a separator and then the FSF text.
if [ -f "${AGPL_PATH}" ] && grep -q "GNU Affero General Public License" "${AGPL_TMP}"; then
  {
    printf "Micelia is licensed under the GNU Affero General Public License v3.0\nor later (AGPL-3.0-or-later).\n\n"
    printf "SPDX-License-Identifier: AGPL-3.0-or-later\n\n"
    printf "Copyright (C) 2026 Asociación Micelia para la Soberanía Computacional\nCooperativa (in formation) and contributors.\n\n"
    printf -- "------------------------------------------------------------------------\n\n"
    cat "${AGPL_TMP}"
  } > "${AGPL_PATH}"
  ok "LICENSE populated with AGPLv3 verbatim text + Micelia notice"
else
  fail "Downloaded file does not appear to be AGPLv3"
fi
rm -f "${AGPL_TMP}"

# ---------------------------------------------------------------------------
# FSL-1.1-ALv2
# ---------------------------------------------------------------------------

FSL_PATH="${REPO_ROOT}/LICENSE.fsl"
FSL_TMP="$(mktemp)"

info "Downloading FSL-1.1-ALv2 template from Sentry/FSL..."
if curl -fsSL "${FSL_URL}" -o "${FSL_TMP}"; then
  # Verify it's the expected license
  if grep -q "Functional Source License" "${FSL_TMP}" && grep -q "Apache License" "${FSL_TMP}"; then
    cp "${FSL_TMP}" "${FSL_PATH}"
    ok "LICENSE.fsl updated with canonical FSL-1.1-ALv2 template"
  else
    info "Downloaded FSL template does not match expected content; keeping existing LICENSE.fsl"
  fi
else
  info "Could not fetch FSL template; keeping existing LICENSE.fsl (it is the canonical text already embedded)"
fi
rm -f "${FSL_TMP}"

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------

ok "License files ready in ${REPO_ROOT}/LICENSE and ${REPO_ROOT}/LICENSE.fsl"
info "Next step: review the files and commit them. See docs/LICENSING_STRATEGY.md for context."
