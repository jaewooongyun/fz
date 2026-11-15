import UIKit

protocol WishlistDependency {
    var wishlistRepository: WishlistRepository { get }
}

final class WishlistComponent {
    let dependency: WishlistDependency

    init(dependency: WishlistDependency) {
        self.dependency = dependency
    }

    var fetchWishlistUseCase: FetchWishlistUseCase {
        FetchWishlistUseCase(repository: dependency.wishlistRepository)
    }
}

protocol WishlistBuildable {
    func build(withListener listener: WishlistListener) -> WishlistRouting
}

final class WishlistBuilder: WishlistBuildable {
    private let component: WishlistComponent

    init(component: WishlistComponent) {
        self.component = component
    }

    func build(withListener listener: WishlistListener) -> WishlistRouting {
        let viewController = WishlistViewController()
        let interactor = WishlistInteractor(
            presenter: viewController,
            fetchWishlistUseCase: component.fetchWishlistUseCase
        )
        interactor.listener = listener
        return WishlistRouter(interactor: interactor, viewController: viewController)
    }
}
