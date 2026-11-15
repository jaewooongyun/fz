import Foundation

final class APIClient {
    static let shared = APIClient()

    private let session = URLSession.shared
    private let baseURL = URL(string: "https://api.example.invalid")!

    func get(path: String) async throws -> Data {
        let (data, _) = try await session.data(from: baseURL.appendingPathComponent(path))
        return data
    }

    func delete(path: String, completion: @escaping (Result<Void, Error>) -> Void) {
        var request = URLRequest(url: baseURL.appendingPathComponent(path))
        request.httpMethod = "DELETE"
        session.dataTask(with: request) { _, _, error in
            if let error {
                completion(.failure(error))
            } else {
                completion(.success(()))
            }
        }.resume()
    }
}
