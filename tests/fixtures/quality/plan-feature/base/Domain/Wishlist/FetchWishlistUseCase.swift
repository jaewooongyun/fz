struct FetchWishlistUseCase {
    let repository: WishlistRepository

    func execute() async throws -> [WishlistItem] {
        try await repository.fetchItems()
    }
}
