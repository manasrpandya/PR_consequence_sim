import { authorize } from "../payments/index";
export const checkout = () => authorize(100);
