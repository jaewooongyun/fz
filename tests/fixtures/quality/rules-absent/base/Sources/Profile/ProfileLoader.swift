import Foundation

protocol ProfileLoaderDelegate: AnyObject {
    func profileLoader(_ loader: ProfileLoader, didLoad name: String)
}

final class ProfileLoader {
    weak var delegate: ProfileLoaderDelegate?

    func load(from data: Data) {
        let name = String(decoding: data, as: UTF8.self)
        delegate?.profileLoader(self, didLoad: name)
    }
}
