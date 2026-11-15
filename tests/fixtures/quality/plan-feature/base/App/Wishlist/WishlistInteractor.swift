import Foundation

protocol WishlistListener: AnyObject {
    func wishlistDidClose()
}

protocol WishlistPresentable: AnyObject {
    var listener: WishlistPresentableListener? { get set }
    func show(items: [WishlistItem])
    func showError(message: String)
}

protocol WishlistPresentableListener: AnyObject {
    func viewDidLoad()
    func didTapClose()
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
}
