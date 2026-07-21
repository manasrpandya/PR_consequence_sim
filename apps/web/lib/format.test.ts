import {describe,expect,it} from "vitest";import {duration,percent} from "./format";
describe("format utilities",()=>{it("formats test durations",()=>{expect(duration(145)).toBe("2m");expect(duration(806)).toBe("13m")});it("formats confidence",()=>expect(percent(.86)).toBe("86%"))});
