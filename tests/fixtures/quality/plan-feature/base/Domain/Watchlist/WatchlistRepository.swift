protocol WatchlistRepository {
    func fetchItems() async throws -> [WatchlistItem]
    func removeItem(id: String) async throws
}
