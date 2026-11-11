"""The auditor's worksheet: a sentence marked up the way a reviewer checks a report.

Verified numbers get a green tick, a number that fails is circled in red pen,
and the reason is written in the margin underneath. The marks are drawn in one
after another when the sheet appears (instantly for reduced motion). Used by the Home hero to
show the fact-check working on a sentence the visitor can edit.
"""

from __future__ import annotations

import html

from ai.factcheck import NumberClaim

TICK = (
    '<svg class="tk" viewBox="0 0 24 24" aria-hidden="true"><path d="M4.5 13.2 9.4 18.4 19.8 5.6" /></svg>'
)


def _note(claim: NumberClaim) -> str:
    """A short margin note for a number that failed."""
    if claim.reason.startswith("Wrong group: "):
        return claim.reason.removeprefix("Wrong group: ")
    if claim.reason.startswith("Wrong direction"):
        return f"{claim.raw} is real, but the change went the other way"
    return f"{claim.raw} is not a figure from this file"


def worksheet_html(text: str, claims: list[NumberClaim], source: str) -> str:
    """The marked-up sentence, its margin notes and a one-line tally. ``text`` is escaped."""
    out, pos = [], 0
    for i, c in enumerate(claims):
        out.append(html.escape(text[pos : c.start]))
        raw = html.escape(text[c.start : c.end])
        step = f' style="--i:{i}"'  # staggers the drawing of each mark
        if c.verified:
            out.append(f'<span class="ok"{step}>{raw}{TICK}<span class="vd-sr"> (verified)</span></span>')
        else:
            out.append(f'<span class="bad"{step}>{raw}<span class="vd-sr"> (not verified)</span></span>')
        pos = c.end
    out.append(html.escape(text[pos:]))

    bad = [c for c in claims if not c.verified]
    notes = "".join(f'<li style="--i:{len(claims) + k}">{html.escape(_note(c))}</li>' for k, c in enumerate(bad))
    ok = len(claims) - len(bad)
    if not claims:
        tally = "No numbers to check yet. Type one in."
    elif not bad:
        tally = "Every number checks out."
    else:
        tally = f"{ok} of {len(claims)} numbers check out."
    return (
        '<figure class="vd-sheet" aria-label="Fact-checked sentence">'
        f'<figcaption>Checked against {html.escape(source)}</figcaption>'
        f'<p class="line">{"".join(out)}</p>'
        + (f'<ul class="notes">{notes}</ul>' if notes else "")
        + f'<p class="tally">{html.escape(tally)}</p></figure>'
    )
