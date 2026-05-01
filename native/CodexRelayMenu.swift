import AppKit
import Foundation

struct CommandResult {
    let code: Int32
    let output: String
}

final class RelayMenuApp: NSObject, NSApplicationDelegate, NSMenuDelegate {
    private let statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
    private let menu = NSMenu()
    private let root: URL

    override init() {
        self.root = RelayMenuApp.findRepoRoot()
        super.init()
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)

        if let button = statusItem.button {
            if let image = NSImage(systemSymbolName: "paperplane.circle.fill", accessibilityDescription: "Codex Relay") {
                button.image = image
            } else {
                button.title = "CR"
            }
            button.toolTip = "Codex Relay"
        }

        menu.delegate = self
        statusItem.menu = menu
        populateMenu()
    }

    func menuNeedsUpdate(_ menu: NSMenu) {
        populateMenu()
    }

    private static func findRepoRoot() -> URL {
        if let url = Bundle.main.url(forResource: "repo-path", withExtension: "txt"),
           let text = try? String(contentsOf: url, encoding: .utf8).trimmingCharacters(in: .whitespacesAndNewlines),
           !text.isEmpty {
            return URL(fileURLWithPath: text)
        }
        return URL(fileURLWithPath: FileManager.default.currentDirectoryPath)
    }

    private func populateMenu() {
        menu.removeAllItems()

        let status = isRelayRunning() ? "Running" : "Not running"
        let header = NSMenuItem(title: "Codex Relay: \(status)", action: nil, keyEquivalent: "")
        header.isEnabled = false
        menu.addItem(header)
        menu.addItem(NSMenuItem.separator())

        menu.addItem(item("Open Status Page", #selector(openStatusPage)))
        menu.addItem(item("Run Doctor", #selector(runDoctor)))
        menu.addItem(item("Restart Relay", #selector(restartRelay)))
        menu.addItem(item("Update Relay", #selector(updateRelay)))
        menu.addItem(NSMenuItem.separator())
        menu.addItem(item("Copy Telegram Commands", #selector(copyTelegramCommands)))
        menu.addItem(item("Open Repo Folder", #selector(openRepoFolder)))
        menu.addItem(item("Open GitHub Repo", #selector(openGitHubRepo)))
        menu.addItem(NSMenuItem.separator())
        menu.addItem(item("Quit", #selector(quit)))
    }

    private func item(_ title: String, _ action: Selector) -> NSMenuItem {
        let item = NSMenuItem(title: title, action: action, keyEquivalent: "")
        item.target = self
        return item
    }

    private func script(_ name: String) -> URL {
        root.appendingPathComponent("scripts").appendingPathComponent(name)
    }

    private func run(_ executable: URL, arguments: [String] = []) -> CommandResult {
        let process = Process()
        let output = Pipe()
        process.executableURL = executable
        process.arguments = arguments
        process.currentDirectoryURL = root
        process.standardOutput = output
        process.standardError = output

        do {
            try process.run()
        } catch {
            return CommandResult(code: 127, output: String(describing: error))
        }

        let data = output.fileHandleForReading.readDataToEndOfFile()
        process.waitUntilExit()
        let text = String(data: data, encoding: .utf8) ?? ""
        return CommandResult(code: process.terminationStatus, output: text)
    }

    private func runScriptInBackground(_ name: String, title: String) {
        DispatchQueue.global(qos: .userInitiated).async {
            let result = self.run(self.script(name))
            DispatchQueue.main.async {
                self.showResult(title: title, result: result)
                self.populateMenu()
            }
        }
    }

    private func showResult(title: String, result: CommandResult) {
        let alert = NSAlert()
        alert.messageText = result.code == 0 ? "\(title) passed" : "\(title) failed"
        alert.informativeText = result.output.isEmpty ? "No output." : String(result.output.prefix(5000))
        alert.alertStyle = result.code == 0 ? .informational : .warning
        alert.addButton(withTitle: "OK")
        NSApp.activate(ignoringOtherApps: true)
        alert.runModal()
    }

    private func isRelayRunning() -> Bool {
        let uid = String(getuid())
        let label = ProcessInfo.processInfo.environment["CODEX_RELAY_LABEL"] ?? "com.codexrelay.agent"
        let result = run(URL(fileURLWithPath: "/bin/launchctl"), arguments: ["print", "gui/\(uid)/\(label)"])
        return result.code == 0 && (result.output.contains("state = running") || result.output.range(of: #"pid = [1-9][0-9]*"#, options: .regularExpression) != nil)
    }

    @objc private func openStatusPage() {
        _ = run(script("status_ui.sh"))
    }

    @objc private func runDoctor() {
        runScriptInBackground("doctor.sh", title: "Doctor")
    }

    @objc private func restartRelay() {
        runScriptInBackground("install_launch_agent.sh", title: "Restart")
    }

    @objc private func updateRelay() {
        runScriptInBackground("update.sh", title: "Update")
    }

    @objc private func copyTelegramCommands() {
        let text = "/alive\n/health\n/screenshot\n/tools\n/latency"
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(text, forType: .string)
    }

    @objc private func openRepoFolder() {
        NSWorkspace.shared.open(root)
    }

    @objc private func openGitHubRepo() {
        if let url = URL(string: "https://github.com/dicnunz/codex-relay") {
            NSWorkspace.shared.open(url)
        }
    }

    @objc private func quit() {
        NSApp.terminate(nil)
    }
}

let app = NSApplication.shared
let delegate = RelayMenuApp()
app.delegate = delegate
app.run()
