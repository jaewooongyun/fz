import Foundation

struct WishlistItemDTO: Decodable {
    let productId: String
    let productTitle: String
    let addedAtEpoch: TimeInterval

    enum CodingKeys: String, CodingKey {
        case productId = "product_id"
        case productTitle = "product_title"
        case addedAtEpoch = "added_at"
    }

    func toEntity() -> WishlistItem {
        WishlistItem(id: productId, title: productTitle, addedAt: Date(timeIntervalSince1970: addedAtEpoch))
    }
}
