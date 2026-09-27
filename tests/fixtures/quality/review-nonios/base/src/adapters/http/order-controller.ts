import { PlaceOrder } from '../../application/place-order';

export interface HttpRequest { body: any; params: Record<string, string> }
export interface HttpResponse { status: number; body: unknown }

export class OrderController {
  constructor(private readonly placeOrder: PlaceOrder) {}

  async create(req: HttpRequest): Promise<HttpResponse> {
    const order = await this.placeOrder.execute(req.body.id, req.body.customerId, req.body.totalAmount);
    return { status: 201, body: { id: order.id } };
  }
}
