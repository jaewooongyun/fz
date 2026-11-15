import UIKit

final class WishlistViewController: UIViewController, WishlistPresentable {
    weak var listener: WishlistPresentableListener?

    private var items: [WishlistItem] = []

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
}
