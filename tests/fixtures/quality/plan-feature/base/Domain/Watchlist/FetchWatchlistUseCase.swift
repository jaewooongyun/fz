struct FetchWatchlistUseCase {
    let repository: WatchlistRepository

    func execute() async throws -> [WatchlistItem] {
        try await repository.fetchItems()
    }
}
