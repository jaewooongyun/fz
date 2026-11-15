import { Order } from '../domain/order';
import { OrderRepositoryPort } from '../domain/order-repository-port';

export interface SqlClient {
  query(sql: string, params: unknown[]): Promise<{ rows: any[] }>;
}

export class PostgresOrderRepository implements OrderRepositoryPort {
  constructor(private readonly db: SqlClient) {}

  async findById(id: string): Promise<Order | undefined> {
    const { rows } = await this.db.query('select * from orders where id = $1', [id]);
    const r = rows[0];
    return r ? new Order(r.id, r.customer_id, r.total_amount, r.status) : undefined;
  }

  async save(order: Order): Promise<void> {
    await this.db.query(
      'insert into orders (id, customer_id, total_amount, status) values ($1, $2, $3, $4) on conflict (id) do update set status = $4',
      [order.id, order.customerId, order.totalAmount, order.status],
    );
  }
}
