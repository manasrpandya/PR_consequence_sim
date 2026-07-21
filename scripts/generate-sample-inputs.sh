#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "$0")/.." && pwd)"
output_dir="$project_root/sample-inputs"
repo_dir="$output_dir/source-repository"

if [[ -e "$output_dir" ]]; then
  echo "Refusing to overwrite existing $output_dir" >&2
  exit 1
fi

mkdir -p "$repo_dir/src" "$repo_dir/tests"

printf '%s\n' \
  'export type CartItem = { price: number; quantity: number };' \
  '' \
  'export function cartTotal(items: CartItem[]): number {' \
  '  return items.reduce((total, item) => total + item.price * item.quantity, 0);' \
  '}' > "$repo_dir/src/cart.ts"

printf '%s\n' \
  'import { describe, expect, it } from "vitest";' \
  'import { cartTotal } from "../src/cart";' \
  '' \
  'describe("cartTotal", () => {' \
  '  it("totals line items", () => {' \
  '    expect(cartTotal([{ price: 12, quantity: 2 }])).toBe(24);' \
  '  });' \
  '});' > "$repo_dir/tests/cart.test.ts"

printf '%s\n' '{"name":"sample-cart","private":true,"scripts":{"test":"vitest run"},"devDependencies":{"vitest":"^2.1.9"}}' > "$repo_dir/package.json"

git -C "$repo_dir" init -q -b main
git -C "$repo_dir" config user.name "PRCS Sample"
git -C "$repo_dir" config user.email "sample@example.invalid"
git -C "$repo_dir" add .
git -C "$repo_dir" commit -qm "base cart total"
base_sha="$(git -C "$repo_dir" rev-parse HEAD)"

git -C "$repo_dir" archive --format=zip --prefix=sample-cart/ -o "$output_dir/sample-project-base.zip" HEAD

printf '%s\n' \
  'export type CartItem = { price: number; quantity: number };' \
  '' \
  'export function cartTotal(items: CartItem[], discountPercent = 0): number {' \
  '  const subtotal = items.reduce((total, item) => total + item.price * item.quantity, 0);' \
  '  const boundedDiscount = Math.min(100, Math.max(0, discountPercent));' \
  '  return subtotal * (1 - boundedDiscount / 100);' \
  '}' > "$repo_dir/src/cart.ts"

printf '%s\n' \
  'import { describe, expect, it } from "vitest";' \
  'import { cartTotal } from "../src/cart";' \
  '' \
  'describe("cartTotal", () => {' \
  '  it("totals line items", () => {' \
  '    expect(cartTotal([{ price: 12, quantity: 2 }])).toBe(24);' \
  '  });' \
  '' \
  '  it("applies a bounded percentage discount", () => {' \
  '    expect(cartTotal([{ price: 20, quantity: 2 }], 25)).toBe(30);' \
  '  });' \
  '});' > "$repo_dir/tests/cart.test.ts"

git -C "$repo_dir" diff --binary > "$output_dir/sample-change.diff"
git -C "$repo_dir" add .
git -C "$repo_dir" commit -qm "add bounded cart discounts"
head_sha="$(git -C "$repo_dir" rev-parse HEAD)"
git -C "$repo_dir" format-patch -1 --stdout > "$output_dir/sample-change.patch"
# A non-delta pack remains a valid Git bundle and is maximally portable to the
# pure-Python Git reader used by the hosted Vercel function.
git -C "$repo_dir" -c pack.window=0 -c pack.depth=0 bundle create "$output_dir/sample-project.bundle" --all
rm -rf "$repo_dir/.git"

printf '%s\n' \
  '# Sample judge inputs' \
  '' \
  'All artifacts represent the same small TypeScript cart change.' \
  '' \
  "- Base commit: \`$base_sha\`" \
  "- Head commit: \`$head_sha\`" \
  '- `sample-project.bundle`: upload in **Git bundle** mode; choose the base and head commits above.' \
  '- `sample-project-base.zip` + `sample-change.diff`: upload together in **Project + diff** mode.' \
  '- `sample-project-base.zip` + `sample-change.patch`: equivalent patch-form test.' \
  '- `source-repository/`: inspect the final source locally; its internal Git metadata is removed after artifact generation.' \
  '' \
  'These files contain no secrets and the application analyzes them without executing their code.' \
  > "$output_dir/README.md"

printf 'Created sample inputs in %s\nBase: %s\nHead: %s\n' "$output_dir" "$base_sha" "$head_sha"
