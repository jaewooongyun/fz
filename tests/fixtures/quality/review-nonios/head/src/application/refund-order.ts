import { Order } from '../domain/order';
import { OrderRepositoryPort } from '../domain/order-repository-port';
import { refundableAmount, RefundPolicy } from '../domain/refund';

export class RefundOrder {
  constructor(private readonly repo: OrderRepositoryPort, private readonly policy: RefundPolicy) {}

  async execute(id: string): Promise<{ order: Order; amount: number }> {
    const order = await this.repo.findById(id);
    if (!order) {
      throw new Error(`order ${id} not found`);
    }
    if (order.status !== 'PAID') {
      throw new Error(`order ${order.id} is not refundable: ${order.status}`);
    }
    order.status = 'REFUNDED';
    this.repo.save(order);
    return { order, amount: refundableAmount(order, this.policy) };
  }
}
