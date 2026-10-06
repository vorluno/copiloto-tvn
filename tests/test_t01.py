"""T01 · Invalid dates and nulls. Owner: B (B-05).

Prepared input: Synthetic CSV with 3 broken dates and 2 nulls.
Expected result: Errors are split out to the quality report, nulls are kept as nulls, the load continues.
Source: test matrix in docs/c-producto-notion-qa.md (section 9 of the challenge).
"""

import pytest


@pytest.mark.skip(reason="T01 not implemented yet (B-05)")
def test_t01():
    """Errors are split out to the quality report, nulls are kept as nulls, the load continues."""
