import SwiftUI
import UIKit

final class WishlistViewController: UIViewController, WishlistPresentable {
    weak var listener: WishlistPresentableListener?

    private var items: [WishlistItem] = []
    private var editToggleWorkItem: DispatchWorkItem?

    override func viewDidLoad() {
        super.viewDidLoad()
        listener?.viewDidLoad()
    }

    func show(items: [WishlistItem]) {
        self.items = items
    }

    func showError(message: String) {
        let alert = UIAlertController(title: nil, message: message, preferredStyle: .alert)
        alert.addAction(UIAlertAction(title: "확인", style: .default))
        present(alert, animated: true)
    }

    func didToggleEditMode(_ isEditing: Bool) {
        editToggleWorkItem?.cancel()
        let item = DispatchWorkItem { [weak self] in
            self?.applyEditMode(isEditing)
        }
        editToggleWorkItem = item
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.3, execute: item)
    }

    private func applyEditMode(_ isEditing: Bool) {
        guard isEditing, let first = items.first else { return }
        let host = UIHostingController(rootView: WishlistEditRow(title: first.title))
        addChild(host)
        view.addSubview(host.view)
        host.didMove(toParent: self)
    }
}
