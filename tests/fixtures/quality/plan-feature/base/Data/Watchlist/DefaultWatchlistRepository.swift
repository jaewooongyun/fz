import Foundation

final class DefaultWatchlistRepository: WatchlistRepository {
    private let client: APIClient

    init(client: APIClient = .shared) {
        self.client = client
    }

    func fetchItems() async throws -> [WatchlistItem] {
        let data = try await client.get(path: "/watchlist")
        return try JSONDecoder().decode([WatchlistItemDTO].self, from: data).map { $0.toEntity() }
    }

    func removeItem(id: String) async throws {
        try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Void, Error>) in
            client.delete(path: "/watchlist/\(id)") { continuation.resume(with: $0) }
        }
    }
}
