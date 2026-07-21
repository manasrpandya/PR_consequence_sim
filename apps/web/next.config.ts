import type { NextConfig } from "next";
import path from "node:path";
const connectSrc=process.env.NODE_ENV==="development"?"'self' http://localhost:8000":"'self'";
const nextConfig: NextConfig = {
  outputFileTracingRoot:path.join(process.cwd(),"../.."),
  async headers(){return [{source:"/(.*)",headers:[
    {key:"X-Content-Type-Options",value:"nosniff"},
    {key:"Referrer-Policy",value:"strict-origin-when-cross-origin"},
    {key:"Permissions-Policy",value:"camera=(), microphone=(), geolocation=()"},
    {key:"Content-Security-Policy",value:`default-src 'self'; connect-src ${connectSrc}; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'`}
  ]}]}
};
export default nextConfig;
