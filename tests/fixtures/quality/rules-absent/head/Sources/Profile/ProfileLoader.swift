import Foundation

protocol ProfileLoaderDelegate: AnyObject {
    func profileLoader(_ loader: ProfileLoader, didLoad name: String)
}

final class ProfileLoader {
    weak var delegate: ProfileLoaderDelegate?

    func load(from data: Data) {
        let name = String(decoding: data, as: UTF8.self)
        guard let delegate = delegate else { return }
        delegate.profileLoader(self, didLoad: name)
    }

    func avatarURL(for rawValue: String) -> URL {
        URL(string: "https://img.example.invalid/avatars/" + rawValue)!
    }
}
