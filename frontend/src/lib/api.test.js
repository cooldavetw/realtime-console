import { RealtimeAPI } from './api';

const originalOverride = process.env.REACT_APP_WS_URL;
afterEach(() => {
  window.history.replaceState({}, '', '/');
  if (originalOverride === undefined) delete process.env.REACT_APP_WS_URL;
  else process.env.REACT_APP_WS_URL = originalOverride;
});

test.each([
  ['/', 'ws://localhost/ws'],
  ['/index.html', 'ws://localhost/ws'],
  ['/fastapi-prod/7/hook/example/', 'ws://localhost/fastapi-prod/7/hook/example/ws'],
  ['/fastapi-prod/7/hook/example/index.html', 'ws://localhost/fastapi-prod/7/hook/example/ws'],
])('resolves WebSocket beside the frontend at %s', (path, expected) => {
  delete process.env.REACT_APP_WS_URL;
  window.history.replaceState({}, '', path);
  expect(new RealtimeAPI().url).toBe(expected);
});

test('preserves environment and explicit URL overrides', () => {
  process.env.REACT_APP_WS_URL = 'wss://backend.example/ws';
  expect(new RealtimeAPI().url).toBe('wss://backend.example/ws');
  expect(new RealtimeAPI({url: 'wss://custom.example/ws'}).url).toBe('wss://custom.example/ws');
});

 describe('connection failures', () => {
  const originalWebSocket = globalThis.WebSocket;
  let socket;
  beforeEach(() => {
    jest.useFakeTimers();
    globalThis.WebSocket = class extends EventTarget {
      constructor() {
        super();
        socket = this;
        this.readyState = 0;
        this.close = jest.fn();
      }
    };
  });
  afterEach(() => {
    globalThis.WebSocket = originalWebSocket;
    jest.useRealTimers();
  });
  test('rejects a stalled handshake after 15 seconds and closes the socket', async () => {
    const api = new RealtimeAPI();
    const result = expect(api.connect()).rejects.toThrow('Could not connect');
    jest.advanceTimersByTime(15000);
    await result;
    expect(socket.close).toHaveBeenCalled();
    expect(api.isConnected()).toBe(false);
  });
  test('rejects when the socket closes before opening', async () => {
    const api = new RealtimeAPI();
    const result = expect(api.connect()).rejects.toThrow('Could not connect');
    socket.dispatchEvent(new Event('close'));
    await result;
  });
  test('clears the handshake timer after opening', async () => {
    const api = new RealtimeAPI();
    const result = api.connect();
    socket.readyState = 1;
    socket.dispatchEvent(new Event('open'));
    await result;
    jest.advanceTimersByTime(15000);
    expect(socket.close).not.toHaveBeenCalled();
    expect(api.isConnected()).toBe(true);
    api.disconnect();
  });
});
