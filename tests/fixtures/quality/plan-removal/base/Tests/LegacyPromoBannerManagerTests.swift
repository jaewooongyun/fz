import XCTest

final class LegacyPromoBannerManagerTests: XCTestCase {
    func testBannerHiddenAfterDismiss() {
        let defaults = UserDefaults(suiteName: "test")!
        let flags = FeatureFlags()
        flags.set(.legacyPromoBanner, enabled: true)
        let manager = LegacyPromoBannerManager(defaults: defaults, flags: flags)
        manager.markDismissed()
        XCTAssertFalse(manager.shouldShowBanner())
    }
}
