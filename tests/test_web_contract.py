from pathlib import Path
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
            "discover-capability",
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
            "No peer devices observed",
            "Unsupported platform",
        ):
            self.assertIn(marker, script)

    def test_collection_coordination_and_capability_recheck_contract(self):
        script = (WEB / "app.js").read_text()
        core = (WEB / "core.mjs").read_text()
        self.assertIn("collectionInFlight", script)
        self.assertIn("collectionInFlight", core)
        self.assertNotIn("passiveInFlight", script)
        self.assertIn('collection: "passive"', script)
        self.assertIn('collection: "active"', script)
        recheck = script.index("loadCapabilities({ reportError: false })")
        completion = script.index('dispatch({ type: "PASSIVE_SUCCESS", snapshot })')
        self.assertLess(recheck, completion)
        self.assertIn('setAttribute("aria-disabled", "true")', script)
        self.assertIn('removeAttribute("aria-disabled")', script)
        self.assertNotIn('elements["refresh-button"].disabled = true', script)
        self.assertIn('unavailable_reason: "dependency_unavailable"', core)
        self.assertIn("available: false", core)
        self.assertIn("const recovered =", core)
        self.assertIn("if (state.collectionInFlight && !action.collection) return state", core)

    def test_discovery_control_is_not_an_unexplained_placeholder(self):
        html = (WEB / "index.html").read_text()
        script = (WEB / "app.js").read_text()
        for marker in (
            'id="discover-capability"',
            "handleDiscoverAction",
            'textContent = "Check Nmap setup"',
            'textContent = "Nmap: unavailable"',
            'textContent = "Nmap: ready"',
            'textContent = "No eligible LAN"',
            "await loadCapabilities()",
        ):
            self.assertIn(marker, html if marker.startswith('id=') else script)
        self.assertIn('addEventListener("click", handleDiscoverAction)', script)

    def test_gateway_path_and_peer_group_contract(self):
        html = (WEB / "index.html").read_text()
        core = (WEB / "core.mjs").read_text()
        script = (WEB / "app.js").read_text()
        css = (WEB / "styles.css").read_text()
        for marker in (
            '"interface_associated_with"',
            '"interface_reaches_link"',
            '"attachment_reaches_gateway"',
            '"interface_reaches_gateway"',
            "not transit hops",
            "groups:",
            "hiddenRelationshipCount",
        ):
            self.assertIn(marker, core)
        self.assertNotIn("l2_segment", core)
        self.assertNotIn("member_of_l2", core)
        self.assertIn("Evidence-backed path, not invented physical topology", html)
        self.assertIn("Other devices are peers, not transit hops", html)
        self.assertIn("renderNetworkGroup", script)
        group_render = script.index('for (const group of layout.groups)')
        edge_render = script.index('for (const edge of layout.edges)')
        self.assertLess(group_render, edge_render)
        self.assertIn("node-access_point", css)
        self.assertIn("node-link_boundary", css)
        self.assertIn("group-lan_peers", css)
        self.assertIn("interface-kind-tunnel", css)

    def test_graph_nodes_show_local_ip_bssid_and_semantic_wifi_details(self):
        script = (WEB / "app.js").read_text()
        css = (WEB / "styles.css").read_text()
        for marker in (
            "preferredIPv4",
            'if (node.kind === "local_host") return address',
            'if (node.kind === "interface") return address',
            'node.properties?.bssid ?? node.mac_addresses?.[0]',
            "PROPERTY_LABELS",
            'hardware_mac_address: "Hardware MAC"',
            'private_wifi_mac_address: "Private Wi-Fi MAC"',
            'bssid: "BSSID"',
            'rssi_dbm: "RSSI"',
            'phy_mode: "PHY mode"',
            'transmit_rate_mbps: "Transmit rate"',
            'appendDetailRow(dl, "Hardware MAC"',
            'appendDetailRow(dl, "Private Wi-Fi MAC"',
            'appendDetailRow(dl, "IP addresses"',
            'appendDetailRow(dl, "From"',
            'appendDetailRow(dl, "To"',
        ):
            self.assertIn(marker, script)
        self.assertNotIn('appendDetailRow(dl, "Identifier"', script)
        self.assertIn("height: clamp(360px, 52vh, 620px)", css)
        self.assertIn(".node:focus, .edge:focus, .network-group:focus { outline: none; }", css)

    def test_canvas_uses_viewbox_camera_full_surface_pan_and_orthogonal_edges(self):
        script = (WEB / "app.js").read_text()
        core = (WEB / "core.mjs").read_text()
        css = (WEB / "styles.css").read_text()
        for marker in (
            "fitCamera",
            "zoomCamera",
            "orthogonalEdgePath",
            'svgElement("path"',
            'setAttribute("viewBox"',
            'addEventListener("pointerdown"',
            "PAN_THRESHOLD = 6",
            "Math.hypot(deltaX, deltaY) <= PAN_THRESHOLD",
            'setPointerCapture(event.pointerId)',
            'classList.add("is-panning")',
            "suppressGraphClick",
            "preventFitUpscale",
        ):
            self.assertIn(marker, script)
        threshold = script.index("Math.hypot(deltaX, deltaY) <= PAN_THRESHOLD")
        capture = script.index('setPointerCapture(event.pointerId)')
        self.assertLess(threshold, capture, "pointer capture must start only after movement proves a pan")
        self.assertNotIn('event.target.closest(".node, .edge")', script)
        self.assertIn("export function fitCamera", core)
        self.assertIn("export function orthogonalEdgePath", core)
        self.assertIn("cursor: grab", css)
        self.assertIn("cursor: grabbing", css)
        self.assertIn("pointer-events: stroke", css)


if __name__ == "__main__":
    unittest.main()
