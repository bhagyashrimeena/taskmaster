export function PageHeader({
  eyebrow,
  title,
  description,
  meta,
}: {
  eyebrow: string;
  title: string;
  description: string;
  meta?: React.ReactNode;
}) {
  return (
    <header className="mb-5 flex flex-col gap-3 md:mb-7 md:flex-row md:items-end md:justify-between">
      <div className="max-w-3xl">
        <span className="section-kicker">{eyebrow}</span>
        <h1 className="mt-2 max-w-4xl font-display text-[2.45rem] leading-[0.98] tracking-[-0.04em] text-ink md:text-[3.35rem]">{title}</h1>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-muted">{description}</p>
      </div>
      {meta}
    </header>
  );
}
