final class LinkRouter {
    func openBanner(_ url: URL) {
        guard url.scheme == "https" else { return }
        open(url)
    }
    func openPromotion(_ url: URL) {
        guard url.scheme == "https" else { return }
        open(url)
    }
}
