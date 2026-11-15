final class WishlistPromoSlot {
    private let manager: LegacyPromoBannerManaging

    init(manager: LegacyPromoBannerManaging) {
        self.manager = manager
    }

    var isVisible: Bool {
        manager.shouldShowBanner()
    }
}
