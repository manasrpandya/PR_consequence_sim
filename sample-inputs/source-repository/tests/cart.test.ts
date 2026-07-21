import { describe, expect, it } from "vitest";
import { cartTotal } from "../src/cart";

describe("cartTotal", () => {
  it("totals line items", () => {
    expect(cartTotal([{ price: 12, quantity: 2 }])).toBe(24);
  });

  it("applies a bounded percentage discount", () => {
    expect(cartTotal([{ price: 20, quantity: 2 }], 25)).toBe(30);
  });
});
