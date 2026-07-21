import { authorize } from "../payments/index";
export const checkout = (amount: number) => {
  if (amount <= 0) throw new Error("invalid amount");
  return authorize(amount);
};
