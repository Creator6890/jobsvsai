"""The environment templates must not drift from what the application actually reads.

A production deployment is provisioned from `.env.production.example`. When a setting exists
in code and in compose but not in that template, the operator has no way to learn it exists
short of reading the application — which is precisely the situation this release exists to
avoid, since the settings in question are the ones that keep AI News switched off.

These tests compare the templates against the Settings model and the compose file rather
than against a hand-maintained list, so a new setting cannot be added without the templates
being updated too.
"""

import pathlib
import re

import pytest

from app.core.config import Settings

pytestmark = pytest.mark.asyncio(loop_scope="session")

# /app in the container, the repo root from a checkout.
ROOT = pathlib.Path("/app") if pathlib.Path("/app/docker-compose.yml").is_file() \
    else pathlib.Path(__file__).resolve().parent.parent.parent

# Not every setting belongs in an operator template: these are internal defaults nobody
# tunes per environment, and listing them would add noise without adding control.
TEMPLATE_EXEMPT = {"NEWS_ENABLED"}   # deprecated; documented as a comment, not a live line


def _declared_in(path: pathlib.Path) -> set[str]:
    """Variable names in a template, whether live or commented out."""
    if not path.is_file():
        return set()
    return set(re.findall(r"^#?\s*(NEWS_[A-Z_0-9]+)\s*=", path.read_text(), re.M))


def _passed_by_compose() -> set[str]:
    return set(re.findall(r"^\s*(NEWS_[A-Z_0-9]+):", (ROOT / "docker-compose.yml").read_text(), re.M))


async def test_compose_passes_every_news_setting_the_app_reads() -> None:
    """`.env` is in `.dockerignore` and is not mounted, so a setting compose does not pass
    can never reach the process, whatever the operator writes in the file."""
    from_model = {name.upper() for name in Settings.model_fields if name.startswith("news_")}
    missing = sorted(from_model - _passed_by_compose())
    assert not missing, f"compose does not pass: {missing}"


@pytest.mark.parametrize("template", [".env.example", ".env.production.example"])
async def test_templates_document_every_setting_compose_passes(template: str) -> None:
    declared = _declared_in(ROOT / template) | TEMPLATE_EXEMPT
    missing = sorted(_passed_by_compose() - declared)
    assert not missing, f"{template} does not mention: {missing}"


async def test_production_template_keeps_ai_news_switched_off() -> None:
    """The whole point of this release is landing safety controls, so the template that
    provisions production must not ship values that turn them on."""
    body = (ROOT / ".env.production.example").read_text()
    for setting in ("NEWS_INGESTION_ENABLED", "NEWS_GENERATION_ENABLED", "NEWS_AUTO_PUBLISH"):
        match = re.search(rf"^{setting}=(.*)$", body, re.M)
        assert match, f"{setting} must be present in the production template"
        assert match.group(1).strip() == "false", (
            f"{setting} must ship as false in the production template"
        )
    # The provider must not be pre-wired either: an accidentally configured provider plus an
    # accidentally enabled flag is the only way this costs money on day one.
    provider = re.search(r"^NEWS_LLM_PROVIDER=(.*)$", body, re.M)
    assert provider and provider.group(1).strip() in ("null", ""), (
        "the production template must not ship a live provider"
    )


async def test_no_template_contains_a_real_looking_secret() -> None:
    for template in (".env.example", ".env.production.example"):
        body = (ROOT / template).read_text()
        assert not re.search(r"AIza[0-9A-Za-z_-]{30,}", body), f"{template} looks like it has a key"
        key_line = re.search(r"^NEWS_LLM_API_KEY=(.*)$", body, re.M)
        if key_line:
            assert key_line.group(1).strip() == "", f"{template} must ship an empty API key"
