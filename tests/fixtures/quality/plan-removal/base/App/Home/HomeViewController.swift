import UIKit

final class HomeViewController: UIViewController {
    private let interactor: HomeInteractor
    private let bannerView = UIView()

    init(interactor: HomeInteractor) {
        self.interactor = interactor
        super.init(nibName: nil, bundle: nil)
    }

    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    override func viewDidAppear(_ animated: Bool) {
        super.viewDidAppear(animated)
        bannerView.isHidden = !interactor.viewDidAppear()
        Analytics.shared.track("promo_banner_impression")
    }
}
