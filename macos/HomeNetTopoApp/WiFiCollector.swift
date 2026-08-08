import AppKit
import CoreLocation
import CoreWLAN
import Foundation

struct WiFiCacheRecord: Codable, Equatable {
    let interface: String
    let ssid: String?
    let bssid: String?
    let hardwareMAC: String?
    let channel: String?
    let rssiDBm: Int?
    let noiseDBm: Int?
    let phyMode: String?
    let transmitRateMbps: Int?

    enum CodingKeys: String, CodingKey {
        case interface
        case ssid
        case bssid
        case hardwareMAC = "hardware_mac_address"
        case channel
        case rssiDBm = "rssi_dbm"
        case noiseDBm = "noise_dbm"
        case phyMode = "phy_mode"
        case transmitRateMbps = "transmit_rate_mbps"
    }
}

struct WiFiCacheEnvelope: Codable {
    let schemaVersion: Int
    let collectedAt: String
    let authorization: String
    let wifi: WiFiCacheRecord?

    enum CodingKeys: String, CodingKey {
        case schemaVersion = "schema_version"
        case collectedAt = "collected_at"
        case authorization
        case wifi
    }
}

@MainActor
final class WiFiCollector: NSObject, ObservableObject, CLLocationManagerDelegate {
    @Published private(set) var authorizationLabel = "Checking location permission…"
    @Published private(set) var currentWiFi: WiFiCacheRecord?
    @Published private(set) var lastUpdated: Date?
    @Published private(set) var errorMessage: String?

    private let locationManager = CLLocationManager()
    private let wifiClient = CWWiFiClient.shared()
    private let cacheInterval: TimeInterval = 5
    private var timer: Timer?

    override init() {
        super.init()
        locationManager.delegate = self
    }

    deinit {
        timer?.invalidate()
    }

    func start() {
        handleAuthorization(locationManager.authorizationStatus, requestIfNeeded: true)
    }

    func requestAuthorizationAndRefresh() {
        NSApp.activate(ignoringOtherApps: true)
        if locationManager.authorizationStatus == .notDetermined {
            locationManager.requestWhenInUseAuthorization()
        } else {
            handleAuthorization(locationManager.authorizationStatus, requestIfNeeded: false)
        }
    }

    func refreshNow() {
        guard isAuthorized(locationManager.authorizationStatus) else {
            requestAuthorizationAndRefresh()
            return
        }
        collectAndPublish()
    }

    func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        handleAuthorization(manager.authorizationStatus, requestIfNeeded: false)
    }

    private func handleAuthorization(_ status: CLAuthorizationStatus, requestIfNeeded: Bool) {
        switch status {
        case .authorizedAlways, .authorizedWhenInUse:
            authorizationLabel = "Location access granted"
            errorMessage = nil
            startTimerIfNeeded()
            collectAndPublish()
        case .notDetermined:
            authorizationLabel = "Location access required for SSID/BSSID"
            stopTimer()
            publishStatusOnly(authorization: "not_determined")
            if requestIfNeeded {
                NSApp.activate(ignoringOtherApps: true)
                locationManager.requestWhenInUseAuthorization()
            }
        case .denied:
            authorizationLabel = "Location access denied"
            errorMessage = "Enable Location access for HomeNetTopo Wi-Fi in System Settings, then refresh."
            stopTimer()
            publishStatusOnly(authorization: "denied")
        case .restricted:
            authorizationLabel = "Location access restricted"
            errorMessage = "macOS currently prevents this app from using Location Services."
            stopTimer()
            publishStatusOnly(authorization: "restricted")
        @unknown default:
            authorizationLabel = "Location permission state is unavailable"
            errorMessage = "macOS returned an authorization state this version of the helper does not recognize."
            stopTimer()
            publishStatusOnly(authorization: "unknown")
        }
    }

    private func isAuthorized(_ status: CLAuthorizationStatus) -> Bool {
        status == .authorizedAlways || status == .authorizedWhenInUse
    }

    private func startTimerIfNeeded() {
        guard timer == nil else { return }
        timer = Timer.scheduledTimer(withTimeInterval: cacheInterval, repeats: true) { [weak self] _ in
            Task { @MainActor in
                self?.collectAndPublish()
            }
        }
    }

    private func stopTimer() {
        timer?.invalidate()
        timer = nil
        currentWiFi = nil
    }

    private func collectAndPublish() {
        guard let interface = wifiClient.interface(), let interfaceName = interface.interfaceName else {
            currentWiFi = nil
            errorMessage = "No default Wi-Fi interface is available."
            publishStatusOnly(authorization: "authorized")
            return
        }

        let ssid = clean(interface.ssid())
        let bssid = canonicalMAC(interface.bssid())
        let hardwareMAC = canonicalMAC(interface.hardwareAddress())
        let channel = interface.wlanChannel().map { String($0.channelNumber) }
        let rssi = measuredValue(interface.rssiValue())
        let noise = measuredValue(interface.noiseMeasurement())
        let transmitRate = positiveRate(interface.transmitRate())
        let phyMode = phyLabel(interface.activePHYMode())

        let associated = ssid != nil || bssid != nil || interface.interfaceMode() == .station
        let record = associated ? WiFiCacheRecord(
            interface: interfaceName,
            ssid: ssid,
            bssid: bssid,
            hardwareMAC: hardwareMAC,
            channel: channel,
            rssiDBm: rssi,
            noiseDBm: noise,
            phyMode: phyMode,
            transmitRateMbps: transmitRate
        ) : nil

        currentWiFi = record
        lastUpdated = Date()
        errorMessage = record == nil ? "Wi-Fi is not currently associated with a network." : nil
        writeCache(authorization: "authorized", wifi: record)
    }

    private func publishStatusOnly(authorization: String) {
        currentWiFi = nil
        lastUpdated = Date()
        writeCache(authorization: authorization, wifi: nil)
    }

    private func writeCache(authorization: String, wifi: WiFiCacheRecord?) {
        let envelope = WiFiCacheEnvelope(
            schemaVersion: 1,
            collectedAt: ISO8601DateFormatter().string(from: Date()),
            authorization: authorization,
            wifi: wifi
        )
        do {
            let data = try JSONEncoder().encode(envelope)
            let directory = try cacheDirectory()
            let target = directory.appendingPathComponent("wifi-current.json", isDirectory: false)
            try data.write(to: target, options: .atomic)
            try FileManager.default.setAttributes([.posixPermissions: 0o600], ofItemAtPath: target.path)
        } catch {
            errorMessage = "Could not publish Wi-Fi evidence for HomeNetTopo: \(error.localizedDescription)"
        }
    }

    private func cacheDirectory() throws -> URL {
        let base = try FileManager.default.url(
            for: .cachesDirectory,
            in: .userDomainMask,
            appropriateFor: nil,
            create: true
        )
        let directory = base.appendingPathComponent("HomeNetTopo", isDirectory: true)
        try FileManager.default.createDirectory(
            at: directory,
            withIntermediateDirectories: true,
            attributes: [.posixPermissions: 0o700]
        )
        return directory
    }

    private func clean(_ value: String?) -> String? {
        guard let value else { return nil }
        let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
        return trimmed.isEmpty ? nil : trimmed
    }

    private func canonicalMAC(_ value: String?) -> String? {
        guard let cleaned = clean(value)?.lowercased().replacingOccurrences(of: "-", with: ":") else { return nil }
        let pattern = #"^[0-9a-f]{2}(?::[0-9a-f]{2}){5}$"#
        return cleaned.range(of: pattern, options: .regularExpression) == nil ? nil : cleaned
    }

    private func measuredValue(_ value: Int) -> Int? {
        value == 0 ? nil : value
    }

    private func positiveRate(_ value: Double) -> Int? {
        value > 0 ? Int(value.rounded()) : nil
    }

    private func phyLabel(_ mode: CWPHYMode) -> String? {
        switch mode {
        case .mode11a: return "802.11a"
        case .mode11b: return "802.11b"
        case .mode11g: return "802.11g"
        case .mode11n: return "802.11n"
        case .mode11ac: return "802.11ac"
        case .mode11ax: return "802.11ax"
        case .modeNone: return nil
        @unknown default: return "PHY mode \(mode.rawValue)"
        }
    }
}
