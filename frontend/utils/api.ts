// API utility - uses proxy route to reach backend via Docker DNS

// Use the proxy endpoint (same origin as frontend)
// The Next.js server proxies to the backend via Docker internal DNS
export const API_URL = '/api/proxy';

export async function fetchAPI(endpoint: string, options: RequestInit = {}) {
  const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const config = {
    ...options,
    headers,
  };

  try {
    // All requests go through the proxy: /api/proxy/auth/token, /api/proxy/chat/sop, etc.
    const response = await fetch(`${API_URL}${endpoint}`, config);

    if (response.status === 401) {
      // Unauthorized - clear token and redirect
      if (typeof window !== 'undefined') {
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        // Avoid redirect loop if already on login
        if (!window.location.pathname.includes('/login')) {
          window.location.href = '/login';
        }
      }
    }

    return response;
  } catch (error) {
    console.error('API Fetch Error:', error);
    throw error;
  }
}

export const getCurrentUser = () => {
  if (typeof window !== 'undefined') {
    const userStr = localStorage.getItem('user');
    return userStr ? JSON.parse(userStr) : null;
  }
  return null;
};

export const isAuthenticated = () => {
  if (typeof window !== 'undefined') {
    const token = localStorage.getItem('token');
    return !!token;
  }
  return false;
};
