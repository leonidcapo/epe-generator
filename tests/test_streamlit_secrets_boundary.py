"""Regression guard for the st.secrets -> os.environ credential boundary.

``streamlit_app.py`` bridges a small, explicit allowlist of environment keys
(``_SECRET_KEYS``) from Streamlit Cloud's ``st.secrets`` into ``os.environ``
so the app can run in the cloud without a local ``.env`` file. That allowlist
must NEVER include ``GOOGLE_SERVICE_ACCOUNT_JSON`` or ``EPE_SHEET_ID``: those
two keys grant read access to a real hospital spreadsheet containing patient
PHI (protected health information). The ``perfilar`` phase that consumes
those credentials is designed to run only on the user's local machine, never
in the cloud deployment.

This boundary previously rested only on manual code review, with nothing to
catch a future accidental addition (e.g. someone "helpfully" widening the
tuple to unblock a cloud feature that touches the PHI sheet). This test
parses ``streamlit_app.py`` with ``ast`` (never importing the module, since
importing it outside ``streamlit run`` can fail or emit runtime warnings) and
asserts the allowlist's exact contents. Do not delete this test as
"redundant" with the source code — it exists precisely to catch drift in
that source code.
"""

import ast
from pathlib import Path

EXPECTED_KEYS = {
    "LLM_PROVIDER",
    "DEEPSEEK_API_KEY",
    "DEEPSEEK_MODEL",
    "PUBMED_API_KEY",
    "AUTH_USER",
    "AUTH_PASSWORD",
}

FORBIDDEN_KEYS = {"GOOGLE_SERVICE_ACCOUNT_JSON", "EPE_SHEET_ID"}


def _extract_secret_keys():
    repo_root = Path(__file__).resolve().parent.parent
    source_path = repo_root / "streamlit_app.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "_SECRET_KEYS":
                    return ast.literal_eval(node.value)

    raise AssertionError("_SECRET_KEYS assignment not found in streamlit_app.py")


def test_secret_keys_match_exact_allowlist_and_exclude_phi_credentials():
    keys = _extract_secret_keys()

    assert len(keys) == 6, (
        f"_SECRET_KEYS should have exactly 6 entries, got {len(keys)}: {keys}"
    )
    assert set(keys) == EXPECTED_KEYS

    assert "GOOGLE_SERVICE_ACCOUNT_JSON" not in keys, (
        "GOOGLE_SERVICE_ACCOUNT_JSON must never be bridged from st.secrets: "
        "it grants access to the PHI-bearing hospital spreadsheet and the "
        "perfilar phase that uses it must remain local-only."
    )
    assert "EPE_SHEET_ID" not in keys, (
        "EPE_SHEET_ID must never be bridged from st.secrets: it identifies "
        "the PHI-bearing hospital spreadsheet and the perfilar phase that "
        "uses it must remain local-only."
    )
    assert not (set(keys) & FORBIDDEN_KEYS)
