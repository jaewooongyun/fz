final class AppContainer {
    let flags = FeatureFlags()

    lazy var promoBannerManager: LegacyPromoBannerManaging = LegacyPromoBannerManager(flags: flags)

    func makeHomeInteractor() -> HomeInteractor {
        HomeInteractor(promoBannerManager: promoBannerManager)
    }

    func makeWishlistPromoSlot() -> WishlistPromoSlot {
        WishlistPromoSlot(manager: promoBannerManager)
    }
}
