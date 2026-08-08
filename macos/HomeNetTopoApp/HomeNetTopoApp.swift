import SwiftUI

@main
struct HomeNetTopoWiFiApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    @StateObject private var collector = WiFiCollector()

    var body: some Scene {
        WindowGroup("HomeNetTopo Wi-Fi Identity") {
            WiFiIdentityView(collector: collector, appDelegate: appDelegate)
                .onAppear {
                    collector.start()
                }
                .onOpenURL { _ in
                    collector.requestAuthorizationAndRefresh()
                }
        }
        .defaultSize(width: 560, height: 460)
    }
}

private struct WiFiIdentityView: View {
    @ObservedObject var collector: WiFiCollector
    @ObservedObject var appDelegate: AppDelegate

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            VStack(alignment: .leading, spacing: 6) {
                Text("HomeNetTopo Wi-Fi Identity")
                    .font(.title2.weight(.semibold))
                Text("macOS protects SSID and BSSID with Location permission. This helper obtains that permission in a real app process and publishes only the current Wi-Fi association to the local HomeNetTopo service.")
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }

            GroupBox("Permission") {
                VStack(alignment: .leading, spacing: 8) {
                    Text(collector.authorizationLabel)
                    if let error = collector.errorMessage {
                        Text(error)
                            .foregroundStyle(.secondary)
                    }
                    HStack {
                        Button("Request Location Access") {
                            collector.requestAuthorizationAndRefresh()
                        }
                        Button("Refresh Wi-Fi") {
                            collector.refreshNow()
                        }
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }

            GroupBox("Current Wi-Fi") {
                if let wifi = collector.currentWiFi {
                    Grid(alignment: .leading, horizontalSpacing: 18, verticalSpacing: 7) {
                        row("Interface", wifi.interface)
                        row("SSID", wifi.ssid)
                        row("BSSID", wifi.bssid)
                        row("Hardware MAC", wifi.hardwareMAC)
                        row("Channel", wifi.channel)
                        row("RSSI", wifi.rssiDBm.map { "\($0) dBm" })
                        row("Noise", wifi.noiseDBm.map { "\($0) dBm" })
                        row("PHY", wifi.phyMode)
                        row("Transmit rate", wifi.transmitRateMbps.map { "\($0) Mbps" })
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                } else {
                    Text("No current association has been published yet.")
                        .foregroundStyle(.secondary)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
            }

            HStack {
                VStack(alignment: .leading, spacing: 3) {
                    Text(appDelegate.loginItemStatus)
                        .font(.callout)
                    if let error = appDelegate.loginItemError {
                        Text(error)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
                Spacer()
                Button("Login Item Settings") {
                    appDelegate.openLoginItemSettings()
                }
            }
        }
        .padding(22)
        .frame(minWidth: 520, minHeight: 420)
    }

    @ViewBuilder
    private func row(_ label: String, _ value: String?) -> some View {
        if let value, !value.isEmpty {
            GridRow {
                Text(label)
                    .fontWeight(.medium)
                Text(value)
                    .textSelection(.enabled)
            }
        }
    }
}
