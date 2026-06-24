import { getApiBase } from './eduevalApi';

let stream = null;
let streamToken = '';
const listeners = new Set();

function closeStream() {
  if (stream) {
    stream.close();
    stream = null;
  }
}

function dispatchEvent(data) {
  listeners.forEach((listener) => {
    try {
      listener(data);
    } catch (error) {
      // Ignore listener failures so other subscribers still receive updates.
    }
  });
}

function ensureStream(token) {
  const nextToken = String(token || '').trim();
  if (!nextToken) return;
  if (stream && streamToken === nextToken) return;
  closeStream();
  streamToken = nextToken;
  const url = `${getApiBase()}/events/stream?access_token=${encodeURIComponent(nextToken)}`;
  stream = new EventSource(url);
  stream.onmessage = (event) => {
    if (!event?.data) return;
    try {
      dispatchEvent(JSON.parse(event.data));
    } catch (error) {
      // Ignore malformed event payloads.
    }
  };
  stream.onerror = () => {
    if (!listeners.size) {
      closeStream();
      streamToken = '';
    }
  };
}

export function subscribeLiveEvents(token, handler) {
  if (typeof handler !== 'function') {
    return () => {};
  }
  listeners.add(handler);
  ensureStream(token);
  return () => {
    listeners.delete(handler);
    if (!listeners.size) {
      closeStream();
      streamToken = '';
    }
  };
}
