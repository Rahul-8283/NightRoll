export type ApiErrorDetail = { field: string; issue: string };

export type ApiErrorBody = {
  error: {
    code: string;
    message: string;
    details: ApiErrorDetail[];
    request_id: string | null;
  };
};

/** Mirrors the backend's standard error shape (`backend/app/errors.py`). */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: ApiErrorDetail[];
  readonly requestId: string | null;

  constructor(status: number, body: ApiErrorBody) {
    super(body.error.message);
    this.name = 'ApiError';
    this.status = status;
    this.code = body.error.code;
    this.details = body.error.details;
    this.requestId = body.error.request_id;
  }
}

/** No response reached the app at all: offline, DNS failure, timeout, or the server is down. */
export class NetworkError extends Error {
  constructor(message = 'Could not reach the server') {
    super(message);
    this.name = 'NetworkError';
  }
}

function isApiErrorBody(value: unknown): value is ApiErrorBody {
  if (typeof value !== 'object' || value === null || !('error' in value)) {
    return false;
  }
  const err = (value as { error: unknown }).error;
  return typeof err === 'object' && err !== null && 'code' in err && 'message' in err;
}

export async function toApiError(status: number, response: Response): Promise<ApiError | NetworkError> {
  try {
    const body: unknown = await response.json();
    if (isApiErrorBody(body)) {
      return new ApiError(status, body);
    }
    return new ApiError(status, {
      error: { code: 'HTTP_ERROR', message: `Request failed with status ${status}`, details: [], request_id: null },
    });
  } catch {
    return new ApiError(status, {
      error: { code: 'HTTP_ERROR', message: `Request failed with status ${status}`, details: [], request_id: null },
    });
  }
}
