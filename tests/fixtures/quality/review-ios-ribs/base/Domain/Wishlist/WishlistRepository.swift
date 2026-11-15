protocol WishlistRepository {
    func fetchItems() async throws -> [WishlistItem]
    func removeItem(id: String) async throws
}
