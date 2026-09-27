import { Order } from '../../domain/order';

export default function canRefund(order: Order, requestedAt: Date): boolean {
  if (order.status !== 'PAID') {
    return false;
  }
  const days = (requestedAt.getTime() - Date.now()) / 86_400_000;
  return days <= 7;
}
