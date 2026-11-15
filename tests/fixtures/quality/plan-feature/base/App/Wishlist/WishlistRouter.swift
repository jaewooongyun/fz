import UIKit

protocol WishlistRouting: AnyObject {
    var viewControllable: UIViewController { get }
}

final class WishlistRouter: WishlistRouting {
    private let interactor: WishlistInteractor
    private let viewController: WishlistViewController

    init(interactor: WishlistInteractor, viewController: WishlistViewController) {
        self.interactor = interactor
        self.viewController = viewController
    }

    var viewControllable: UIViewController { viewController }
}
