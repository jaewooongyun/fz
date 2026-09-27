import SwiftUI

final class WatchlistEditRowModel: ObservableObject {
    @Published var isSelected = false

    func toggle() {
        isSelected.toggle()
    }
}

struct WatchlistEditRow: View {
    let title: String
    @ObservedObject var model = WatchlistEditRowModel()

    var body: some View {
        HStack {
            Image(systemName: model.isSelected ? "checkmark.circle.fill" : "circle")
                .foregroundColor(Color(red: 0.92, green: 0.2, blue: 0.24))
            Text(title)
                .foregroundColor(DSColor.textPrimary)
        }
        .onTapGesture { model.toggle() }
    }
}
