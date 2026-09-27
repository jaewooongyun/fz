import Foundation

final class HomeInteractor {
    private let promoBannerManager: LegacyPromoBannerManaging

    init(promoBannerManager: LegacyPromoBannerManaging) {
        self.promoBannerManager = promoBannerManager
    }

    func viewDidAppear() -> Bool {
        promoBannerManager.shouldShowBanner()
    }

    func didDismissBanner() {
        promoBannerManager.markDismissed()
    }
}
