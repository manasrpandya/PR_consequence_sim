export type CartItem = { price: number; quantity: number };

export function cartTotal(items: CartItem[], discountPercent = 0): number {
  const subtotal = items.reduce((total, item) => total + item.price * item.quantity, 0);
  const boundedDiscount = Math.min(100, Math.max(0, discountPercent));
  return subtotal * (1 - boundedDiscount / 100);
}
