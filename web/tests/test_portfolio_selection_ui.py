from pathlib import Path


INDEX = (Path(__file__).resolve().parent.parent / "static" / "index.html").read_text()


def test_card_click_selects_while_details_is_explicit_action():
    assert "toggleSelected(el.dataset.slug)" in INDEX
    assert 'data-details="${esc(i.slug)}"' in INDEX
    assert "go({ v: el.dataset.details })" in INDEX


def test_stars_and_selection_are_independent():
    assert "selected: new Set()" in INDEX
    assert "stars: new Set()" in INDEX
    assert 'const STARS_KEY = "ventures.stars"' in INDEX
    assert "state.selected.has(slug)" in INDEX
    assert "state.stars.has(slug)" in INDEX
    assert "function toggleStarred(slug)" in INDEX
    assert 'state.scope = p.get("scope") === "starred"' in INDEX
    assert 'p.set("scope", state.scope)' in INDEX


def test_set_detail_actions_are_contextual():
    assert 'data-open-selected' in INDEX
    assert 'data-clear-selected' in INDEX
    assert "Open stars" not in INDEX
    assert "async function renderVentureSet(label, slugs)" in INDEX


def test_card_and_star_expose_separate_pressed_state():
    assert 'aria-selected="${state.selected.has(i.slug)}"' in INDEX
    assert 'aria-pressed="${state.stars.has(i.slug)}"' in INDEX
    assert 'data-star="${esc(i.slug)}"' in INDEX


def test_portfolio_card_row_mode_is_clear_and_columns_are_curated():
    assert 'p.get("mode") === "rows"' in INDEX
    assert 'state.portfolioBasePromise = api("api/portfolio?" + key)' in INDEX
    assert "visiblePortfolioRecords(payload)" in INDEX
    assert 'class="portfolio-table"' in INDEX
    assert "e.shiftKey" in INDEX
    assert 'aria-label="Portfolio layout"' in INDEX
    assert "All properties" not in INDEX


def test_venture_app_shell_exposes_initial_modules():
    assert 'aria-label="Venture application modules"' in INDEX
    for module in ("overview", "work", "evidence", "agents", "prompts"):
        assert f'["{module}"' in INDEX
