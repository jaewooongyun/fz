import UIKit

protocol WatchlistDependency {
    var watchlistRepository: WatchlistRepository { get }
}

final class WatchlistComponent {
    let dependency: WatchlistDependency

    init(dependency: WatchlistDependency) {
        self.dependency = dependency
    }

    var fetchWatchlistUseCase: FetchWatchlistUseCase {
        FetchWatchlistUseCase(repository: dependency.watchlistRepository)
    }
}

protocol WatchlistBuildable {
    func build(withListener listener: WatchlistListener) -> WatchlistRouting
}

final class WatchlistBuilder: WatchlistBuildable {
    private let component: WatchlistComponent

    init(component: WatchlistComponent) {
        self.component = component
    }

    func build(withListener listener: WatchlistListener) -> WatchlistRouting {
        let viewController = WatchlistViewController()
        let interactor = WatchlistInteractor(
            presenter: viewController,
            fetchWatchlistUseCase: component.fetchWatchlistUseCase
        )
        interactor.listener = listener
        return WatchlistRouter(interactor: interactor, viewController: viewController)
    }
}
