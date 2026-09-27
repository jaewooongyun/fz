import Foundation

protocol LegacyPromoBannerManaging: AnyObject {
    func shouldShowBanner() -> Bool
    func markDismissed()
}

final class LegacyPromoBannerManager: LegacyPromoBannerManaging {
    static let dismissedAtKey = "legacyPromoBannerDismissedAt"

    private let defaults: UserDefaults
    private let flags: FeatureFlags

    init(defaults: UserDefaults = .standard, flags: FeatureFlags) {
        self.defaults = defaults
        self.flags = flags
    }

    func shouldShowBanner() -> Bool {
        guard flags.isEnabled(.legacyPromoBanner) else { return false }
        return defaults.object(forKey: Self.dismissedAtKey) == nil
    }

    func markDismissed() {
        defaults.set(Date(), forKey: Self.dismissedAtKey)
        Analytics.shared.track("promo_banner_dismiss")
    }
}
