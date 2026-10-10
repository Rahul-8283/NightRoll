// Shared stand-in for pages whose features are built in later phases.
export function Placeholder({ title, phase }: { title: string; phase: string }) {
  return (
    <section>
      <h1>{title}</h1>
      <p>Not built yet. Planned in {phase}.</p>
    </section>
  )
}
