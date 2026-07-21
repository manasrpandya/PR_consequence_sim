// @vitest-environment jsdom
import {afterEach,describe,expect,it,vi} from "vitest";
import {intakeApi} from "./api";

afterEach(()=>vi.unstubAllGlobals());

describe("production API routing and errors",()=>{
  it("uses the same-origin GitHub route outside development",async()=>{
    const fetchMock=vi.fn().mockResolvedValue(new Response(JSON.stringify({valid:true}),{status:200,headers:{"content-type":"application/json"}}));
    vi.stubGlobal("fetch",fetchMock);
    await intakeApi.inspectGithub("https://github.com/vercel/next.js/pull/82995");
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/github/inspect",expect.objectContaining({method:"POST"}));
  });

  it("replaces the browser's generic Failed to fetch message",async()=>{
    vi.stubGlobal("fetch",vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    await expect(intakeApi.inspectGithub("https://github.com/vercel/next.js/pull/82995")).rejects.toThrow("analysis service could not be reached");
  });

  it("shows structured GitHub errors with a request reference",async()=>{
    const body={error:{code:"github_not_found",message:"That public pull request was not found or is not accessible.",request_id:"request-123"}};
    vi.stubGlobal("fetch",vi.fn().mockResolvedValue(new Response(JSON.stringify(body),{status:404,headers:{"content-type":"application/json","x-request-id":"request-123"}})));
    await expect(intakeApi.inspectGithub("https://github.com/example/missing/pull/999999")).rejects.toThrow("not found or is not accessible. Reference: request-123");
  });
});
