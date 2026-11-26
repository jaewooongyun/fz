final class OtherRouter {
    func a(_ url: URL) { if url.scheme == "https" { open(url) } }
    func b(_ url: URL) { if url.scheme?.lowercased() == "https" { open(url) } }
    func c(_ url: URL) { if ["http", "https"].contains(url.scheme ?? "") { open(url) } }
    func d(_ kind: String) { if kind == "movie" { showMovie() } }
    func e(_ kind: String) { if kind == "movie" { showMovie() } }
    func f(_ kind: String) { if "episode" == kind { showEpisode() } }
}
