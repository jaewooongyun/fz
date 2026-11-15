import { PostgresOrderRepository } from '../adapters/postgres-order-repository';
import { Order } from './order';

export interface RefundPolicy {
  repository: PostgresOrderRepository;
  feeRate: number;
}

export function refundableAmount(order: Order, policy: RefundPolicy): number {
  return order.totalAmount * (1 - policy.feeRate);
}
