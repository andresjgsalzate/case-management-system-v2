import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

async function proxyRequest(
  request: NextRequest,
  params: { path?: string[] }
): Promise<NextResponse> {
  const path = params.path?.join("/") ?? "";
  const backendUrl = `${BACKEND_URL}/api/v1/${path}`;

  // Forward query params
  const { searchParams } = request.nextUrl;
  const queryString = searchParams.toString();
  const targetUrl = queryString ? `${backendUrl}?${queryString}` : backendUrl;

  // Build headers to forward
  const headers: Record<string, string> = {
    "content-type": request.headers.get("content-type") ?? "application/json",
  };

  const authorization = request.headers.get("authorization");
  if (authorization) {
    headers["authorization"] = authorization;
  }

  // Forward the request
  const body =
    request.method !== "GET" && request.method !== "HEAD"
      ? await request.text()
      : undefined;

  let backendResponse: Response;
  try {
    backendResponse = await fetch(targetUrl, {
      method: request.method,
      headers,
      body,
    });
  } catch (err) {
    const isConnRefused =
      err instanceof Error && err.message.includes("ECONNREFUSED");
    return NextResponse.json(
      {
        detail: isConnRefused
          ? "El servidor backend no está disponible"
          : "Error al conectar con el servidor",
      },
      { status: 503 }
    );
  }

  // Forward the response — 204/205 No Content cannot have a body
  if (backendResponse.status === 204 || backendResponse.status === 205) {
    return new NextResponse(null, { status: backendResponse.status });
  }

  const contentType = backendResponse.headers.get("content-type") ?? "application/json";

  // SSE: pipe the stream directly — never buffer it
  if (contentType.includes("text/event-stream") && backendResponse.body) {
    return new NextResponse(backendResponse.body, {
      status: backendResponse.status,
      headers: {
        "content-type": "text/event-stream",
        "cache-control": "no-cache",
        "x-accel-buffering": "no",
        "connection": "keep-alive",
      },
    });
  }

  const responseBody = await backendResponse.text();
  return new NextResponse(responseBody, {
    status: backendResponse.status,
    headers: { "content-type": contentType },
  });
}

export async function GET(
  request: NextRequest,
  { params }: { params: { path?: string[] } }
) {
  return proxyRequest(request, params);
}

export async function POST(
  request: NextRequest,
  { params }: { params: { path?: string[] } }
) {
  return proxyRequest(request, params);
}

export async function PUT(
  request: NextRequest,
  { params }: { params: { path?: string[] } }
) {
  return proxyRequest(request, params);
}

export async function PATCH(
  request: NextRequest,
  { params }: { params: { path?: string[] } }
) {
  return proxyRequest(request, params);
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: { path?: string[] } }
) {
  return proxyRequest(request, params);
}
