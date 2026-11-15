enum FeatureFlag: String {
    case legacyPromoBanner = "legacy_promo_banner"
    case newCheckout = "new_checkout"
}

final class FeatureFlags {
    private var values: [FeatureFlag: Bool] = [:]

    func isEnabled(_ flag: FeatureFlag) -> Bool {
        values[flag] ?? false
    }

    func set(_ flag: FeatureFlag, enabled: Bool) {
        values[flag] = enabled
    }
}
