# Interface polish — November 8, 2026

The employee and administrator interfaces retain Ace's navy text, teal accents, white cards, light gray backgrounds, and rounded corners. The changes use the existing HTML/JavaScript application, with no new dependencies or external services.

## Changes

- Employee home: tighter spacing, a more prominent search panel, readable supporting cards, and explicit verified-quotation labels. The privacy warning stays beside the question field. Verified quotations use teal, policy discrepancies use amber, and service errors use red.
- Overview: four real account/document counts with decorative inline vector icons, a prominent Find & Fix alert, and compact synchronization health with a Knowledge Management link. No usage metrics or activity data were added. Existing fictional usage totals were removed from the isolated preview.
- Account management: clearer tables, hover states, consistent actions, and account-specific deactivation dialogs with a safe cancel action and inline failure feedback. A visible, accessible explanation describes why deactivation is disabled at the two-admin minimum. Requests still use the existing authenticated API and CSRF client.
- Knowledge Management: clear source verification and last-success information, readable local timestamps, improved document tables, and a collapsed Advanced Settings section containing folder-ID configuration. Existing sync, refresh, and folder controls remain available.
- Office directory: consistent primary-code and alternate-code badges. Lilburn's LIL primary code and ADC alias remain intact.
- Find & Fix Log: one row per backend-supplied policy issue, concise heading-based issue titles, Needs Review badges, filename and office information, and an expanded comparison dialog. Both exact source quotations and their filenames, headings/pages, and offices remain intact. Comparisons stack on mobile. A sticky dialog header keeps the close control available while scrolling. Human review, authorized Drive correction, and re-sync are explained explicitly; the interface never selects the correct policy.
- Shared usability: consistent spacing, controls, badges, visible keyboard focus, reduced-motion support, and keyboard-accessible table scrolling. Background refresh waits while a dialog is open or focus is in the section, protecting comparisons and edits. Section navigation starts at the top without unexpectedly scrolling keyboard focus.
- Browser validation: escaped literal hyphens in the existing account-identifier and folder-ID patterns so current Chrome accepts them under HTML's Unicode regular-expression rules. Allowed values and backend validation remain unchanged.

## Files changed

| File | Purpose |
| --- | --- |
| `frontend/ui.css` | Shared colors, control sizing, focus, and motion foundations |
| `frontend/style.css` | Employee spacing, search prominence, contrast, and responsive layout |
| `frontend/index.html` | Consistent informational-card accents |
| `frontend/script.js` | Explicit verified-quotation labels and citation classes |
| `frontend/admin.css` | Dashboard, tables, statuses, comparison dialogs, and mobile layouts |
| `frontend/admin.js` | Shared cards/icons, local date formatting, modal focus/close controls, review workflow, concise titles, and preview cleanup |
| `frontend/live-admin.js` | Presentation and existing-action wiring across the six live admin sections |
| `backend/main.py` | Add only `ui.css` to the existing static-asset allowlist |
| `tests/employee_renderer.cjs` | Locate quotation/citation nodes by purpose after the new label |
| `tests/test_admin_dashboard_ui.cjs` | Confirmation, cancellation, denied mutation, administrator minimum, timestamps, concise titles, preserved evidence, and form-pattern regressions |
| `tests/test_admin_dashboard.py` | Verify the shared stylesheet is served and unapproved assets remain blocked |
| `docs/interface-polish.md` | This change and verification report |

The sole server change is the static-asset allowlist entry. OAuth, ingestion, retrieval/ranking, quotation verification, conflict detection, discrepancy backend logic, database models, authentication, CSRF, office filtering, and document restrictions were not changed.

## Verification

- `python -m pytest -q`: **435 passed**, with existing dependency deprecation warnings.
- `node --test tests/test_auth_client.cjs tests/test_employee_search_ui.cjs tests/test_admin_dashboard_ui.cjs`: **31 passed**.
- JavaScript syntax checks and `git diff --check`: passed.
- Headless Chrome against a separate temporary SQLite database and generated fictional documents: all six admin sections checked at **320, 375, 768, 1024, and 1440 pixels**, with no page-level horizontal overflow. Table regions retain horizontal scrolling and keyboard access.
- Actual browser actions: administrator/employee sign-in, logout, both view-switch links, all six admin navigation links, employee creation/edit/PIN reset/deactivation/cancel/reactivation, administrator creation/password replacement/deactivation, minimum-admin disabled state, office creation, folder settings save, and re-sync.
- Actual employee searches: verified result, conflicting quotations, and office selection exercised through the existing APIs. Frontend tests also cover missing results, unavailable service, expired sessions, and CSRF recovery.
- The synthetic discrepancy scan produced one distinct issue. The displayed row count matched the API, and both dialog quotations matched the detail response exactly. Mobile stacking, scrolling to the second source, keyboard focus, Escape, and the persistent close control were checked.
- Final full browser run: **zero JavaScript/console errors and zero failed CSS/JavaScript asset requests**. A final targeted check also verified the sticky dialog header and all four vector KPI icons under the existing Content Security Policy.

No confidential Ace documents, private database contents, or live Drive responses were inspected. Browser screenshots contain fictional data only and were saved under `/private/tmp/ace-visual-polish-checks/`.

## Remaining notes

No remaining layout defects were observed at the tested Chrome widths. Wide tables intentionally scroll horizontally on narrow screens; long comparisons scroll inside their dialog. Safari and Firefox were not visually tested. Live Google Drive connectivity and actual confidential discrepancy contents were not exercised; verification used isolated fictional sources and the existing regression suites.

Restart FastAPI if it is not running with automatic reload, so the existing asset route recognizes the new shared stylesheet. Reload the browser afterward. No migration, reseeding, or re-sync is required for the visual changes.
