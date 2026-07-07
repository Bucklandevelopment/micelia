# Contributor License Agreement (CLA) — Micelia

**Version**: 1.0 (cooperative) — **pending external legal review**
**Effective**: 2026-05-24 (provisional)
**Applies to**: every contribution made to the Micelia repository after the date above.

> **Honest disclosure (added in T5.4 post-review)**: This CLA has NOT yet
> been reviewed by an attorney specialized in cooperative intellectual
> property. The two cooperative clauses (§4 no-relicensing without
> supermajority and §5 reversion on capture) are innovative and may not
> be enforceable in every jurisdiction without adjustments — particularly
> in Spanish civil law (Art. 43-45 LPI), where copyright transfers may
> require explicit acts of the rightsholder rather than automatic
> "deemed transfers". The maintainers commit to obtaining specialized
> legal review (estimated €500-1500) before v0.2. Until then, contributors
> are accepting this CLA understanding that the cooperative protections
> are provisional. Standard contributions (§2 copyright grant, §3 patent
> grant, §7 disclaimer) follow the Apache CLA / Software Conservancy
> templates and are defensible.

---

## What is this and why does it exist

This Contributor License Agreement is the contract you accept when you submit any contribution (code, documentation, design, translation) to the Micelia project. It exists to (a) give the project the legal certainty it needs to license outputs under AGPLv3 and FSL-1.1-ALv2, and (b) protect the project against captures that would betray its cooperative mission.

The Micelia CLA derives from the Apache Individual CLA and the Software Freedom Conservancy template, with two cooperative clauses added. Read carefully — these two clauses are the heart of what makes this CLA different from standard CLAs.

---

## 1. Definitions

- **"You"** is the person submitting the Contribution. If you submit on behalf of an employer, "You" includes that employer; ensure you have the right to bind them before signing.
- **"Contribution"** is any work of authorship intentionally submitted to the Micelia project: source code, documentation, designs, translations, configurations, or anything else stored in the repository.
- **"The Project"** is the Micelia software project, currently maintained by the Asociación Micelia para la Soberanía Computacional Cooperativa (in formation), hereafter "the Steward".
- **"Active Node"** is a contributor who has merged at least one Contribution in the trailing 12 months.

---

## 2. Grant of copyright license

You hereby grant the Steward and recipients of software distributed by the Steward a perpetual, worldwide, non-exclusive, royalty-free, irrevocable copyright license to reproduce, prepare derivative works of, publicly display, publicly perform, sublicense, and distribute your Contributions and such derivative works under the terms of:

- AGPL-3.0-or-later for orchestrator components, and
- FSL-1.1-ALv2 (converting to Apache 2.0 after two years) for modules so designated by the file header.

You retain copyright ownership of your Contributions. You are licensing them, not transferring them.

---

## 3. Grant of patent license

You hereby grant the Steward and recipients a perpetual, worldwide, non-exclusive, royalty-free, irrevocable (except as stated in this section) patent license to make, have made, use, offer to sell, sell, import, and otherwise transfer your Contribution, where such license applies only to those patent claims licensable by You that are necessarily infringed by your Contribution alone or by combination of your Contribution with the work to which it was submitted.

If any entity institutes patent litigation against You or any other entity alleging that your Contribution, or the work to which You have contributed, constitutes direct or contributory patent infringement, then any patent licenses granted to that entity under this Agreement for that Contribution or work shall terminate as of the date such litigation is filed.

---

## 4. Cooperative Clause A — No relicensing without supermajority of Active Nodes

The Steward may NOT relicense your Contribution under terms more permissive than AGPLv3 (e.g. MIT, Apache 2.0) or under proprietary terms unless:

1. A formal proposal is published with at least 60 days of public notice, and
2. At least **two-thirds (2/3) of Active Nodes** vote in favor in a public vote with a quorum of at least 50% of Active Nodes participating.

This clause survives any change of Steward identity. It is binding on any successor entity.

The intent is to prevent a future Steward (under acquisition pressure, board capture, or financial distress) from unilaterally moving Micelia to a less-protective license, which would harm both contributors and users.

A "more restrictive" relicensing (e.g. AGPL → SSPL, or AGPL → source-available with shorter conversion window) is permitted with simple majority of Active Nodes, since it would only strengthen the anti-capture posture.

---

## 5. Cooperative Clause B — Reversion on capture

> **Construction note (T5.4)**: The "irrevocable" copyright license granted
> in §2 is NOT revoked by this clause. Rather, this clause operates as a
> **conditional sublicense of the Steward's right to act on behalf of
> contributors**. The original Steward's exclusive operational rights are
> deemed transferred to a Successor Steward elected by Active Nodes; the
> §2 grant to "recipients of software distributed by the Steward" remains
> intact for downstream users. In plain language: your code does not get
> taken back from anyone using it; only the operational authority moves
> to a new cooperative entity.

If the Steward:

1. Is acquired by, merged into, or otherwise absorbed by a for-profit entity with more than 50 employees; or
2. Changes its bylaws to remove cooperative governance (one-member-one-vote at the legal level); or
3. Concentrates effective control of repository write access in fewer than three persons not approved by the Active Nodes; or
4. Ceases to operate Micelia development for a continuous period of 18 months;

then all copyright licenses granted by You under this Agreement to the Steward are deemed transferred, by the operation of this Agreement, to a **Successor Steward** elected by the Active Nodes through a public vote with the same quorum and supermajority as Clause A.

The original Steward retains a non-exclusive license sufficient to comply with prior distributions but loses the right to accept new Contributions or to grant new sublicenses on behalf of Contributors.

The intent is to make hostile acquisition of the Steward strategically pointless: any acquirer ends up with code they cannot exclusively control.

---

## 6. Representations

You represent that:

1. You are legally entitled to grant the licenses above. If your employer has rights to intellectual property you create, you have received permission to make Contributions on behalf of that employer, or your employer has waived such rights in writing for Micelia.
2. Each Contribution is your original creation OR you clearly mark third-party material in the Contribution and ensure its license permits incorporation under AGPLv3 / FSL.
3. You will notify the Steward if any circumstance affecting these representations changes.

---

## 7. Disclaimer

You provide your Contributions on an "AS IS" basis, without warranties or conditions of any kind, either express or implied, including without limitation warranties of TITLE, NON-INFRINGEMENT, MERCHANTABILITY, or FITNESS FOR A PARTICULAR PURPOSE.

---

## 8. How to accept

By submitting a pull request, you accept this Agreement. The PR template will include a checkbox stating:

> [ ] I have read and accept the Micelia CLA (`docs/CLA.md`).

For first-time contributors, the project maintainers will request explicit confirmation in the PR conversation. No external signing system is required.

For contributions made on behalf of an employer, please include in your PR description:

> "I am contributing on behalf of <Employer Name>, which has reviewed and accepted the Micelia CLA. Contact: <employer signatory email>."

---

## 9. Plain-language summary (non-binding)

- You keep your copyright.
- The project gets the licenses it needs to ship Micelia under AGPL/FSL.
- The project CANNOT silently move your work to a more permissive license — it requires 2/3 of active contributors to vote yes.
- If the project is acquired or captured, your work reverts to a new cooperative entity that the active contributors elect.
- These two protections are why this CLA exists. Standard CLAs (Apache, Software Conservancy) don't include them.

---

## 10. Questions

Open an issue tagged `[cla-question]` on the Micelia repository, or contact the Steward at cla@micelia.org (mailbox to be provisioned with the trademark filing).

---

*This CLA is licensed under CC0-1.0 (public domain). Other cooperative projects are encouraged to adapt it.*
