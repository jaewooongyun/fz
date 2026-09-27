import UIKit

protocol WatchlistRouting: AnyObject {
    var viewControllable: UIViewController { get }
}

final class WatchlistRouter: WatchlistRouting {
    private let interactor: WatchlistInteractor
    private let viewController: WatchlistViewController

    init(interactor: WatchlistInteractor, viewController: WatchlistViewController) {
        self.interactor = interactor
        self.viewController = viewController
    }

    var viewControllable: UIViewController { viewController }
}
