import { Order } from './order';

export interface OrderRepositoryPort {
  findById(id: string): Promise<Order | undefined>;
  save(order: Order): Promise<void>;
}
