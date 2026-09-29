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
