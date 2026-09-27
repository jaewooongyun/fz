import Foundation

struct WatchlistItemDTO: Decodable {
    let contentId: String
    let contentTitle: String
    let addedAtEpoch: TimeInterval

    enum CodingKeys: String, CodingKey {
        case contentId = "content_id"
        case contentTitle = "content_title"
        case addedAtEpoch = "added_at"
    }

    func toEntity() -> WatchlistItem {
        WatchlistItem(id: contentId, title: contentTitle, addedAt: Date(timeIntervalSince1970: addedAtEpoch))
    }
}
