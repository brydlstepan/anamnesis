export function TypeDot({ type }: { type: string }) {
  return <span className="type-dot" style={{ background: `var(--t-${type})` }} />;
}
