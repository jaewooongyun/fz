import Observation
import SwiftUI

@Observable
final class WishlistEditBannerState {
    var selectedCount = 0
}

struct WishlistEditBanner: View {
    @State private var state = WishlistEditBannerState()

    var body: some View {
        Text("\(state.selectedCount)개 선택됨")
            .foregroundColor(ThemeColor.textPrimary)
    }
}
