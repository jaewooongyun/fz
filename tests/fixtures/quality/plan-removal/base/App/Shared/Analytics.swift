final class Analytics {
    static let shared = Analytics()

    func track(_ event: String) {
        print("[analytics] \(event)")
    }
}
