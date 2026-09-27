import Foundation

protocol WatchlistListener: AnyObject {
    func watchlistDidClose()
    func watchlistDidChange(count: Int)
}

protocol WatchlistPresentable: AnyObject {
    var listener: WatchlistPresentableListener? { get set }
    func show(items: [WatchlistItem])
    func showError(message: String)
}

protocol WatchlistPresentableListener: AnyObject {
    func viewDidLoad()
    func didTapClose()
    func didTapRemove(itemID: String)
}

final class WatchlistInteractor: WatchlistPresentableListener {
    weak var listener: WatchlistListener?

    private let presenter: WatchlistPresentable
    private let fetchWatchlistUseCase: FetchWatchlistUseCase
    private var items: [WatchlistItem] = []

    init(presenter: WatchlistPresentable, fetchWatchlistUseCase: FetchWatchlistUseCase) {
        self.presenter = presenter
        self.fetchWatchlistUseCase = fetchWatchlistUseCase
        presenter.listener = self
    }

    func viewDidLoad() {
        Task { @MainActor in
            do {
                items = try await fetchWatchlistUseCase.execute()
                presenter.show(items: items)
            } catch {
                presenter.showError(message: "목록을 불러오지 못했습니다")
            }
        }
    }

    func didTapClose() {
        listener?.watchlistDidClose()
    }

    func didTapRemove(itemID: String) {
        doRemoveAndLog(itemID)
    }

    private func doRemoveAndLog(_ itemID: String) {
        guard let listener = listener else { return }
        APIClient.shared.delete(path: "/watchlist/\(itemID)") { result in
            switch result {
            case .success:
                self.items.removeAll { $0.id == itemID }
                self.presenter.show(items: self.items)
                listener.watchlistDidChange(count: self.items.count)
                print("removed \(itemID)")
            case .failure:
                self.presenter.showError(message: "삭제하지 못했습니다")
            }
        }
    }
}
