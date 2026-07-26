import { auth } from "@/auth";
import { getEventBus } from "@/lib/events";
import { NextRequest } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET(req: NextRequest) {
  const session = await auth();
  if (!session?.user) {
    return new Response("Unauthorized", { status: 401 });
  }

  const userId = (session.user as any).id as string;
  const bus = getEventBus();

  const encoder = new TextEncoder();
  let clientId: string | null = null;

  const stream = new ReadableStream({
    start(controller) {
      clientId = bus.addClient(userId, controller);

      // Send initial connection event
      controller.enqueue(
        encoder.encode(
          `data: ${JSON.stringify({
            type: "system",
            payload: { message: "Connected to AEON real-time stream" },
            user_id: userId,
            timestamp: new Date().toISOString(),
          })}\n\n`
        )
      );
    },
    cancel() {
      if (clientId) {
        bus.removeClient(clientId);
      }
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}
