import { settlementSchema } from "./schema";
export const validatesSettlement = settlementSchema.idempotencyKey === "required";
