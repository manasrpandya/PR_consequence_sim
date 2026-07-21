import { settlementSchema } from "../database/schema";
export const authorize = (amount: number) => amount > 0 && Boolean(settlementSchema);
