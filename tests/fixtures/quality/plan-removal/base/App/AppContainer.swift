final class AppContainer {
    let flags = FeatureFlags()

    lazy var promoBannerManager: LegacyPromoBannerManaging = LegacyPromoBannerManager(flags: flags)

    func makeHomeInteractor() -> HomeInteractor {
        HomeInteractor(promoBannerManager: promoBannerManager)
    }

    func makeWatchlistPromoSlot() -> WatchlistPromoSlot {
        WatchlistPromoSlot(manager: promoBannerManager)
    }
}
