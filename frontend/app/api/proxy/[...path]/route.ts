import { NextRequest, NextResponse } from 'next/server';

// Backend URL - accessible from Next.js server (inside Docker)
const BACKEND_URL = process.env.BACKEND_URL || 'http://exim-chat-backend:3333';

export async function GET(request: NextRequest) {
    return proxyRequest(request, 'GET');
}

export async function POST(request: NextRequest) {
    return proxyRequest(request, 'POST');
}

export async function PUT(request: NextRequest) {
    return proxyRequest(request, 'PUT');
}

export async function PATCH(request: NextRequest) {
    return proxyRequest(request, 'PATCH');
}

export async function DELETE(request: NextRequest) {
    return proxyRequest(request, 'DELETE');
}

async function proxyRequest(request: NextRequest, method: string) {
    try {
        // Get the path after /api/proxy/
        const url = new URL(request.url);
        const path = url.pathname.replace('/api/proxy', '');
        const search = url.search;

        const targetUrl = `${BACKEND_URL}${path}${search}`;

        // Forward headers (except host)
        const headers = new Headers();
        request.headers.forEach((value, key) => {
            if (key.toLowerCase() !== 'host') {
                headers.set(key, value);
            }
        });

        // Build fetch options
        const fetchOptions: RequestInit = {
            method,
            headers,
        };

        // Forward body for non-GET requests
        if (method !== 'GET' && method !== 'HEAD') {
            const body = await request.text();
            if (body) {
                fetchOptions.body = body;
            }
        }

        // Make request to backend
        const response = await fetch(targetUrl, fetchOptions);

        // Forward response
        const responseHeaders = new Headers();
        response.headers.forEach((value, key) => {
            responseHeaders.set(key, value);
        });

        const responseBody = await response.text();

        return new NextResponse(responseBody, {
            status: response.status,
            statusText: response.statusText,
            headers: responseHeaders,
        });
    } catch (error) {
        console.error('Proxy error:', error);
        return NextResponse.json(
            { error: 'Failed to proxy request to backend' },
            { status: 502 }
        );
    }
}
