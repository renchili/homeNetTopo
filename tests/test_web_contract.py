from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


class WebContractTests(unittest.TestCase):
    def test_required_assets_and_hooks_exist(self):
        for name in ("index.html", "core.mjs", "app.js", "styles.css"):
            self.assertTrue((WEB / name).is_file(), name)
        html = (WEB / "index.html").read_text()
        for hook in (
            "refresh-button",
            "discover-button",
            "export-button",
            "topology-svg",
            "discover-dialog",
            "status-region",
            "status-heading",
            "dialog-error",
        ):
            self.assertIn(f'id="{hook}"', html)

    def test_active_post_has_custom_header_and_passive_post(self):
        script = (WEB / "app.js").read_text()
        self.assertIn('"X-HomeNetTopo-Request": "1"', script)
        self.assertIn('/api/v1/topology/refresh', script)
        self.assertIn('/api/v1/discover', script)
        self.assertIn("new Set(selected.map", script)

    def test_assets_have_no_external_fetch_or_asset_urls(self):
        combined = "\n".join(path.read_text() for path in WEB.iterdir() if path.is_file())
        self.assertNotRegex(combined, r"(?:fetch|src|href)\s*\(?\s*[=:\"]+\s*https?://")
        self.assertNotIn("@import url(http", combined)
        html = (WEB / "index.html").read_text()
        self.assertNotRegex(html, r"<script(?![^>]+src=)[^>]*>")
        self.assertNotRegex(html, r"<style[^>]*>")

    def test_dom_updates_avoid_html_string_sinks(self):
        script = (WEB / "app.js").read_text()
        self.assertNotIn("innerHTML", script)
        self.assertNotIn("insertAdjacentHTML", script)
        self.assertIn("replaceChildren", script)

    def test_accessibility_and_reduced_motion_hooks(self):
        html = (WEB / "index.html").read_text()
        css = (WEB / "styles.css").read_text()
        self.assertIn("aria-live", html)
        self.assertIn("<dialog", html)
        self.assertIn("prefers-reduced-motion", css)
        self.assertIn(":focus-visible", css)

    def test_status_and_validation_states_have_focus_owners_and_recovery_logic(self):
        html = (WEB / "index.html").read_text()
        script = (WEB / "app.js").read_text()
        self.assertRegex(html, r'id="status-heading"[^>]*tabindex="-1"')
        self.assertRegex(html, r'id="dialog-error"[^>]*role="alert"[^>]*tabindex="-1"')
        for marker in (
            "focusStatusHeading",
            "focusDialogValidation",
            "requestAnimationFrame",
            'setAttribute("aria-invalid", "true")',
            "restoreFocus: false",
            "No neighbor devices observed",
            "Unsupported platform",
        ):
            self.assertIn(marker, script)

    def test_passive_loading_keeps_trigger_focusable_and_dependency_failure_disables_discovery(self):
        script = (WEB / "app.js").read_text()
        core = (WEB / "core.mjs").read_text()
        self.assertIn("passiveInFlight", script)
        self.assertIn('setAttribute("aria-disabled", "true")', script)
        self.assertIn('removeAttribute("aria-disabled")', script)
        self.assertNotIn('elements["refresh-button"].disabled = true', script)
        self.assertIn("dependencyUnavailable", script)
        self.assertIn("Install or restore Nmap", script)
        self.assertIn('unavailable_reason: "dependency_unavailable"', core)
        self.assertIn("available: false", core)


if __name__ == "__main__":
    unittest.main()
