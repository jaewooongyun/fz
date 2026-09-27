import Foundation

final class ProfileService {
    private var cache: [String: String] = [:]

    func cachedName(for id: String) -> String? {
        cache[id]
    }

    func store(name: String, for id: String) {
        cache[id] = name
    }

    func refreshOnMain(_ update: () -> Void) {
        DispatchQueue.main.sync {
            update()
        }
    }
}
