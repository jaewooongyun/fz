final class HomeVC {
    func a() {
        cellA.onVisible = { [weak self] in
            guard let self, !isVerticalScrolling else { return }
            self.log(1)
        }
    }
    func b() {
        cellB.onVisible = { [weak self] in
            guard let self, !isVerticalScrolling else { return }
            self.log(2)
        }
    }
    func c() {
        cellC.onVisible = { [weak self] in
            guard let self else { return }
            self.log(3)
        }
    }
}
