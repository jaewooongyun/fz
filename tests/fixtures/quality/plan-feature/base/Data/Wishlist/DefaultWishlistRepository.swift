import Foundation

final class DefaultWishlistRepository: WishlistRepository {
    private let client: APIClient

    init(client: APIClient = .shared) {
        self.client = client
    }

    func fetchItems() async throws -> [WishlistItem] {
        let data = try await client.get(path: "/wishlist")
        return try JSONDecoder().decode([WishlistItemDTO].self, from: data).map { $0.toEntity() }
    }

    func removeItem(id: String) async throws {
        try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Void, Error>) in
            client.delete(path: "/wishlist/\(id)") { continuation.resume(with: $0) }
        }
    }
}
