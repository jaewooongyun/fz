import SwiftUI

final class WishlistEditRowModel: ObservableObject {
    @Published var isSelected = false

    func toggle() {
        isSelected.toggle()
    }
}

struct WishlistEditRow: View {
    let title: String
    @ObservedObject var model = WishlistEditRowModel()

    var body: some View {
        HStack {
            Image(systemName: model.isSelected ? "checkmark.circle.fill" : "circle")
                .foregroundColor(Color(red: 0.92, green: 0.2, blue: 0.24))
            Text(title)
                .foregroundColor(ThemeColor.textPrimary)
        }
        .onTapGesture { model.toggle() }
    }
}
