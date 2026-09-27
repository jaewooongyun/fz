import Observation
import SwiftUI

@Observable
final class WatchlistEditBannerState {
    var selectedCount = 0
}

struct WatchlistEditBanner: View {
    @State private var state = WatchlistEditBannerState()

    var body: some View {
        Text("\(state.selectedCount)개 선택됨")
            .foregroundColor(DSColor.textPrimary)
    }
}
