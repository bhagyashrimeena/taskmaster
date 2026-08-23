const backendUrl = process.env.WEALTH_COPILOT_BACKEND_URL ?? "http://127.0.0.1:8001";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const upstream = await fetch(`${backendUrl}/api/v1/events/stream`, {
    cache: "no-store",
    headers: { Accept: "text/event-stream" },
    signal: request.signal,
  });

  if (!upstream.ok || !upstream.body) {
    return Response.json(
      { detail: "The financial-day event stream is temporarily unavailable." },
      { status: upstream.status || 503 },
    );
  }

  return new Response(upstream.body, {
    status: 200,
    headers: {
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "Content-Type": "text/event-stream; charset=utf-8",
      "X-Accel-Buffering": "no",
    },
  });
}
