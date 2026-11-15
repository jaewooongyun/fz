final class StoreVC {
    func a() {
        productCellA.onSelect = { [weak self] in
            guard let self, !isCheckoutLocked else { return }
            self.log(1)
        }
    }
    func b() {
        productCellB.onSelect = { [weak self] in
            guard let self, !isCheckoutLocked else { return }
            self.log(2)
        }
    }
    func c() {
        productCellC.onSelect = { [weak self] in
            guard let self else { return }
            self.log(3)
        }
    }
}
