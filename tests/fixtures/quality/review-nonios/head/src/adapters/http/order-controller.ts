import { PlaceOrder } from '../../application/place-order';
import { RefundOrder } from '../../application/refund-order';
import canRefund from './refundHelper';

export interface HttpRequest { body: any; params: Record<string, string> }
export interface HttpResponse { status: number; body: unknown }

export class OrderController {
  constructor(private readonly placeOrder: PlaceOrder, private readonly refundOrder: RefundOrder) {}

  async create(req: HttpRequest): Promise<HttpResponse> {
    const order = await this.placeOrder.execute(req.body.id, req.body.customerId, req.body.totalAmount);
    return { status: 201, body: { id: order.id } };
  }

  async refund(req: HttpRequest): Promise<HttpResponse> {
    const result = await this.refundOrder.execute(req.params.id);
    if (!canRefund(result.order, new Date())) {
      return { status: 409, body: { error: 'refund window closed' } };
    }
    return { status: 200, body: { amount: result.amount } };
  }
}
