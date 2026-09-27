import SwiftUI

struct ProfileCardView: View {
    let profile: ProfileResponse

    var body: some View {
        Text(profile.displayName)
    }
}
