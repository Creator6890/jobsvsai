"""The single public-activation gate for every public read path.

An occupation row existing in `occupations` with a row in `occupation_scores` is
NOT sufficient to publish it. An occupation is public only when it is active and
its canonical identity carries a publication record whose activation_status is
'public'. That record is written by the editorial promotion workflow, so this
predicate is what keeps demo, staged, candidate, and editorially-rejected
occupations off the public site.

Admin surfaces deliberately do NOT apply this predicate: reviewers need to see
occupations precisely while they are still unpublished.
"""

ALLOWED_ALIASES = frozenset({"o", "occupation", "target"})


def public_occupation_predicate(alias: str = "o") -> str:
    """Return a SQL boolean fragment restricting `alias` to public occupations.

    EXISTS is used rather than a join so that an occupation carrying several
    publication rows (multiple locales or geographies) can never fan out into
    duplicate result rows.
    """
    if alias not in ALLOWED_ALIASES:
        raise ValueError(f"Unsupported occupation alias for the publication gate: {alias!r}")
    return f"""
        {alias}.is_active
        AND EXISTS (
          SELECT 1
          FROM canonical_occupation_identities gate_identity
          JOIN occupation_publications gate_publication
            ON gate_publication.identity_id = gate_identity.id
          WHERE gate_identity.jobs_vs_ai_occupation_id = {alias}.id
            AND gate_publication.activation_status = 'public'
        )
    """.strip()
