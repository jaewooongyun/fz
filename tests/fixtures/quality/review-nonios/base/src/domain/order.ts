export type OrderStatus = 'PENDING' | 'PAID' | 'REFUNDED' | 'CANCELLED';

export class Order {
  constructor(
    public readonly id: string,
    public readonly customerId: string,
    public readonly totalAmount: number,
    public status: OrderStatus,
  ) {}

  assertMutable(): void {
    if (this.status !== 'PENDING') {
      throw new Error(`order ${this.id} is not mutable: ${this.status}`);
    }
  }
}
