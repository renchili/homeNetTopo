import AppKit
import Combine
import Foundation
import ServiceManagement

@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate, ObservableObject {
    @Published private(set) var loginItemStatus = "Checking launch-at-login status…"
    @Published private(set) var loginItemError: String?

    func applicationDidFinishLaunching(_ notification: Notification) {
        if ProcessInfo.processInfo.arguments.contains("--unregister-login-item") {
            unregisterLoginItemAndTerminate()
            return
        }

        NSApp.setActivationPolicy(.regular)
        NSApp.activate(ignoringOtherApps: true)
        registerLoginItemIfNeeded()
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        false
    }

    func registerLoginItemIfNeeded() {
        let service = SMAppService.mainApp
        switch service.status {
        case .enabled:
            loginItemStatus = "Launch at login enabled"
            loginItemError = nil
        case .requiresApproval:
            loginItemStatus = "Launch at login needs approval"
            loginItemError = "Approve HomeNetTopo Wi-Fi in System Settings > General > Login Items."
        case .notRegistered:
            do {
                try service.register()
                refreshLoginItemStatus()
            } catch {
                loginItemStatus = "Launch at login not enabled"
                loginItemError = error.localizedDescription
            }
        case .notFound:
            loginItemStatus = "Launch-at-login registration unavailable"
            loginItemError = "macOS could not locate the installed HomeNetTopo Wi-Fi application."
        @unknown default:
            loginItemStatus = "Launch-at-login state unavailable"
            loginItemError = nil
        }
    }

    func openLoginItemSettings() {
        SMAppService.openSystemSettingsLoginItems()
    }

    private func refreshLoginItemStatus() {
        switch SMAppService.mainApp.status {
        case .enabled:
            loginItemStatus = "Launch at login enabled"
            loginItemError = nil
        case .requiresApproval:
            loginItemStatus = "Launch at login needs approval"
            loginItemError = "Approve HomeNetTopo Wi-Fi in System Settings > General > Login Items."
        case .notRegistered:
            loginItemStatus = "Launch at login not registered"
        case .notFound:
            loginItemStatus = "Launch-at-login registration unavailable"
        @unknown default:
            loginItemStatus = "Launch-at-login state unavailable"
        }
    }

    private func unregisterLoginItemAndTerminate() {
        do {
            if SMAppService.mainApp.status != .notRegistered {
                try SMAppService.mainApp.unregister()
            }
        } catch {
            // Uninstall remains best-effort here. The deployment script removes
            // the local app and cache even if macOS retains a disabled record.
        }
        NSApp.terminate(nil)
    }
}
