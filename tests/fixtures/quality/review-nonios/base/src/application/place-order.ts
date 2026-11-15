import { Order } from '../domain/order';
import { OrderRepositoryPort } from '../domain/order-repository-port';

export class PlaceOrder {
  constructor(private readonly repo: OrderRepositoryPort) {}

  async execute(id: string, customerId: string, totalAmount: number): Promise<Order> {
    if (!Number.isInteger(totalAmount) || totalAmount <= 0) {
      throw new Error('totalAmount must be a positive integer (KRW)');
    }
    const order = new Order(id, customerId, totalAmount, 'PENDING');
    await this.repo.save(order);
    return order;
  }
}
