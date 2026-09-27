import UIKit

final class WatchlistViewController: UIViewController, WatchlistPresentable {
    weak var listener: WatchlistPresentableListener?

    private var items: [WatchlistItem] = []

    override func viewDidLoad() {
        super.viewDidLoad()
        listener?.viewDidLoad()
    }

    func show(items: [WatchlistItem]) {
        self.items = items
    }

    func showError(message: String) {
        let alert = UIAlertController(title: nil, message: message, preferredStyle: .alert)
        alert.addAction(UIAlertAction(title: "확인", style: .default))
        present(alert, animated: true)
    }
}
