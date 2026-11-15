import Foundation

protocol WishlistListener: AnyObject {
    func wishlistDidClose()
    func wishlistDidChange(count: Int)
}

protocol WishlistPresentable: AnyObject {
    var listener: WishlistPresentableListener? { get set }
    func show(items: [WishlistItem])
    func showError(message: String)
}

protocol WishlistPresentableListener: AnyObject {
    func viewDidLoad()
    func didTapClose()
    func didTapRemove(itemID: String)
}

final class WishlistInteractor: WishlistPresentableListener {
    weak var listener: WishlistListener?

    private let presenter: WishlistPresentable
    private let fetchWishlistUseCase: FetchWishlistUseCase
    private var items: [WishlistItem] = []

    init(presenter: WishlistPresentable, fetchWishlistUseCase: FetchWishlistUseCase) {
        self.presenter = presenter
        self.fetchWishlistUseCase = fetchWishlistUseCase
        presenter.listener = self
    }

    func viewDidLoad() {
        Task { @MainActor in
            do {
                items = try await fetchWishlistUseCase.execute()
                presenter.show(items: items)
            } catch {
                presenter.showError(message: "목록을 불러오지 못했습니다")
            }
        }
    }

    func didTapClose() {
        listener?.wishlistDidClose()
    }

    func didTapRemove(itemID: String) {
        doRemoveAndLog(itemID)
    }

    private func doRemoveAndLog(_ itemID: String) {
        guard let listener = listener else { return }
        APIClient.shared.delete(path: "/wishlist/\(itemID)") { result in
            switch result {
            case .success:
                self.items.removeAll { $0.id == itemID }
                self.presenter.show(items: self.items)
                listener.wishlistDidChange(count: self.items.count)
                print("removed \(itemID)")
            case .failure:
                self.presenter.showError(message: "삭제하지 못했습니다")
            }
        }
    }
}
