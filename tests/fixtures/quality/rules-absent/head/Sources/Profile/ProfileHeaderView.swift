import SwiftUI

final class ProfileHeaderModel: ObservableObject {
    @Published var isFollowing = false
}

struct ProfileHeaderView: View {
    let name: String
    @ObservedObject var model = ProfileHeaderModel()

    var body: some View {
        VStack(alignment: .leading) {
            Text(name)
                .foregroundColor(Color(red: 0.1, green: 0.1, blue: 0.12))
            Button(model.isFollowing ? "팔로잉" : "팔로우") {
                model.isFollowing.toggle()
            }
        }
    }
}
