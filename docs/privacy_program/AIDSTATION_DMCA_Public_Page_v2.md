# AIDSTATION DMCA Public Page Content

**Status:** v2 — cross-reference unversioning cleanup (no substantive change since the v1 Batch 8 draft)
**Owner:** Privacy Lead (Designated Agent)
**Last Updated:** May 19, 2026
**Companion docs:** `AIDSTATION_DMCA_Designated_Agent_Spec`, `AIDSTATION_DMCA_Templates`
**Closes:** D-102
**Backlog refs:** `Privacy_Program_Backlog_v1.md`

---

## 0. Scope

This document contains the content to be published at `aidstation.pro/dmca`. Audience: anyone (potential complaining parties, AIDSTATION users curious about the policy, legal counsel evaluating the service).

The published page satisfies AIDSTATION's obligations under:

- §512(c)(2) — publication of agent contact information
- §512(i)(1)(A) — informing subscribers of the repeat-infringer policy

**Posture.** Calibrated to operator-favorable per DMCA Spec v2 — meets statutory disclosure requirements, does not volunteer additional commitments.

**Status of this document.** Draft for counsel review. The page is intended to be plain-language readable while remaining legally precise; counsel should verify both qualities before publication.

---

## 1. Page Content — publish as `aidstation.pro/dmca`

### PAGE CONTENT BEGINS

---

# Copyright and DMCA

**Last updated:** [PUBLICATION DATE]

AIDSTATION respects the intellectual property of others and asks the same of those who use our service. This page explains how to report copyright infringement and how AIDSTATION responds.

## Designated Agent

AIDSTATION has designated an agent to receive notifications of claimed copyright infringement, in accordance with the Digital Millennium Copyright Act, 17 U.S.C. §512.

**DMCA Designated Agent**
AIDSTATION Pro, LLC
509 Williams Avenue
Cleburne, TX 76033
United States

Email: `info@aidstation.pro`
Phone: [TBD]

AIDSTATION is registered in the U.S. Copyright Office DMCA Designated Agent Directory.

## Reporting Claimed Infringement

If you believe content on AIDSTATION infringes your copyright, you may submit a notice to our Designated Agent at the address above. A valid notice must include all six of the elements specified in 17 U.S.C. §512(c)(3):

1. A physical or electronic signature of the copyright owner or person authorized to act on their behalf
2. Identification of the copyrighted work claimed to have been infringed (or a representative list, if multiple works)
3. Identification of the material claimed to be infringing, with sufficient information for us to locate it (URL, in-product path, or other identifier)
4. Your contact information (address, telephone, email)
5. A good-faith statement that the use is not authorized by the copyright owner, its agent, or the law
6. A statement, under penalty of perjury, that the information in the notice is accurate and that you are authorized to act on behalf of the copyright owner

A notice template is available at `aidstation.pro/dmca/notice-template`. You may submit a notice in any form that includes the required elements; the template is provided for convenience.

**Notices missing required elements may not be acted on.** We may, at our discretion, contact you to request that you correct a notice with technical defects (e.g., missing contact information). We are under no obligation to do so.

**Misrepresentation in a notice may expose you to liability** for damages under §512(f).

## How AIDSTATION Responds

AIDSTATION evaluates each notice consistently with §512(c). When a notice is substantially compliant and the material is within our control, we typically take down or disable access to the material expeditiously. Actual processing time depends on the complexity of the notice, the volume of content involved, and the availability of personnel.

When we act on a notice:

- We promptly notify the user whose content has been removed and provide them with a copy of the notice (your contact information may be redacted on documented request, consistent with applicable law and at AIDSTATION's discretion)
- The user has the right to submit a counter-notification under §512(g)
- The action is recorded in our internal logs

We may decline to act on, or escalate for further review, notices that appear facially abusive — for example, notices that target plainly fair use, that target criticism or commentary, that appear retaliatory or harassing, or that are submitted by parties who are clearly not the right-holder.

## Counter-Notification

If your content has been removed and you believe it was a mistake or misidentification, you may submit a counter-notification under §512(g). A counter-notice template is available at `aidstation.pro/dmca/counter-notice-template`.

A valid counter-notice must include all of the elements specified in 17 U.S.C. §512(g)(3), including consent to U.S. federal court jurisdiction. The counter-notice process has legal consequences. We encourage you to consult an attorney before submitting one.

We will forward valid counter-notices to the original complaining party. If we do not receive notice of a lawsuit within not less than 10 nor more than 14 business days, we will typically restore the material.

**Misrepresentation in a counter-notice may expose you to liability** for damages under §512(f).

## Repeat Infringer Policy

AIDSTATION may terminate the accounts of users determined to be repeat infringers, in appropriate circumstances. Whether circumstances are appropriate is determined by AIDSTATION at its discretion. We may consider a range of factors, including the number of notices that have resulted in takedown against the account, the nature and severity of the alleged infringements, the presence or absence of valid counter-notifications, the user's overall conduct on the service, and any other relevant context.

We may, but are not required to, issue warnings to users before terminating an account. We may, but are not required to, articulate the specific factors leading to a termination decision beyond a general statement.

Terminated users may contact `info@aidstation.pro` to request reconsideration. Reconsideration is at our discretion.

## What This Page Is Not

This page is informational. It is not legal advice. AIDSTATION is a host of user-generated content; we are not a substitute for legal counsel on copyright matters. If you are unsure whether to submit a notice or counter-notice, consult an attorney.

This page does not create third-party rights, does not warrant any specific timing or outcome on any notice or counter-notice, and does not waive any rights or defenses AIDSTATION may have under §512 or otherwise.

AIDSTATION may update this page and its DMCA procedures at any time. Material changes will be reflected in an updated version of this page.

## Other Intellectual Property Matters

For trademark, patent, right-of-publicity, or other intellectual property concerns not covered by the DMCA process, contact us at `info@aidstation.pro`. Such matters are handled outside this DMCA process.

---

### PAGE CONTENT ENDS

---

## 2. Implementation Notes

- **Hosting.** The page lives at `aidstation.pro/dmca`. The template URLs referenced (`aidstation.pro/dmca/notice-template`, `aidstation.pro/dmca/counter-notice-template`) require the templates from `AIDSTATION_DMCA_Templates` to be similarly published.
- **Linking.** The page should be linked from the website footer and referenced in T&C (pending consistency-pass edit per D-104). An in-app link in any future Help → Legal area is recommended but not required at v1.
- **Phone number.** The `[TBD]` placeholder for the Designated Agent phone number must be filled before USCO registration (per Backlog D-101).
- **Last updated date.** Update when material changes are made. The "may update at any time" language preserves discretion; the visible date provides honest signaling without creating a commitment to versioning.
- **Page title and URL slug.** "Copyright and DMCA" is the recommended page title; the URL slug `/dmca` is the conventional choice and matches the email alias.

---

## 3. Cross-Spec Touchpoints

| Document | Relationship |
|---|---|
| `AIDSTATION_DMCA_Designated_Agent_Spec` | Primary spec. This page is the user-facing surface of §2.4 (publication), §3 (notice elements), §5 (counter-notification), §6 (repeat-infringer policy) |
| `AIDSTATION_DMCA_Templates` | Templates 1 and 2 are linked from this page |
| `AIDSTATION_Terms_and_Conditions` | T&C copyright section (pending) will reference this page |
| `AIDSTATION_Privacy_Policy` | DMCA process is a separate processing activity (proposed PA-16 in RoPA); PP does not need to reference this page directly |
| `AIDSTATION_Repeat_Infringer_Internal_Guideline` | The §"Repeat Infringer Policy" on this page is the public-facing version; the internal guideline governs application |

---

## 4. Gut Check

### 4.1 Risks

- **The "facially abusive notices" paragraph is a public signal that AIDSTATION pushes back on bad notices.** Operator-favorable but may be read by aggressive complainants as a defensive posture to work around. Defensible — courts have generally protected hosts' right to evaluate notice validity.
- **No published timing windows is the right posture per DMCA Spec v2 but will surprise some readers.** Complainants who expect a 24–48-hour acknowledgment or takedown commitment will not find it here. Intentional. Matches the spec.
- **The repeat-infringer language is generic by design.** Readers may push for more specifics ("how many strikes?"). The DMCA Spec v2 reasoning applies — public-facing policy is intentionally discretionary; internal application is governed by the unpublished guideline (D-106).
- **The "Other Intellectual Property Matters" paragraph routes trademark/patent to `info@aidstation.pro` without specifying a process.** That's because we don't have one yet. Defensible at v1 but worth tracking.

### 4.2 What might be missing

- **Accessibility (WCAG-compatible page design).** Not addressed in this content draft; that's a frontend concern.
- **A visual "checklist" view** of what a complete notice contains. The numbered list serves the function but could be presented more visually.
- **Multi-language versions.** EU launch will require at least selected languages.
- **A retraction process.** If a complaining party retracts their notice, the page doesn't explain how content gets restored. Folds into general operational handling.

### 4.3 Best argument against this content

A counter-position: **the page is too long.** Some providers publish a much shorter page (just agent contact + a 2–3 sentence policy summary). Arguments:

- Shorter is more readable and complaining parties are unlikely to read the whole thing anyway
- More text = more surface area for things to commit to or contradict elsewhere

The defense for the length:

- §512 disclosure requirements call for substantive content (notice elements, counter-notification process, repeat-infringer policy)
- A bare-bones page may not satisfy the "informs subscribers and account holders" requirement of §512(i)(1)(A)
- Length is calibrated to legal completeness; further trimming would risk substance

Page content stands.

---

## Change Log

| Version | Date | Changes | Author |
|---|---|---|---|
| v1 | May 19, 2026 | Initial public page content. §512(c)(2) and §512(i)(1)(A) disclosure requirements met. Operator-favorable posture matches DMCA Spec v2 — no published timing commitments, no published numeric repeat-infringer threshold, discretionary multi-factor policy. Closes D-102. | Privacy Lead |
| v2 | May 30, 2026 | Contact-address consolidation to the two approved addresses: `help@aidstation.pro` for user support (including privacy / data-rights requests) and `info@aidstation.pro` for formal, legal, security, and DMCA correspondence. No other changes. | Privacy Lead |

---

*Cross-reference cleanup (v2, 2026-05-30): inline references to companion documents were converted to unversioned logical names per Rule #12, so they no longer go stale when a companion document is revised. No substantive content changes. See `Privacy_Program_Consistency_Sweep_Report_v1.md`.*

