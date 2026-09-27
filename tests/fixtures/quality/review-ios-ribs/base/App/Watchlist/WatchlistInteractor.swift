import Foundation

protocol WatchlistListener: AnyObject {
    func watchlistDidClose()
}

protocol WatchlistPresentable: AnyObject {
    var listener: WatchlistPresentableListener? { get set }
    func show(items: [WatchlistItem])
    func showError(message: String)
}

protocol WatchlistPresentableListener: AnyObject {
    func viewDidLoad()
    func didTapClose()
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
}
