import { RealtimeEventHandler } from './event_handler.js';
import { RealtimeUtils } from './utils.js';

export class RealtimeAPI extends RealtimeEventHandler {
  /**
   * Create a new RealtimeAPI instance
   * @param {{url?: string, debug?: boolean}} [settings]
   * @returns {RealtimeAPI}
   */
  constructor({ url, debug } = {}) {
    super();
    const location = globalThis.location;
    this.defaultUrl = process.env.REACT_APP_WS_URL || (location
      ? `${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}/ws`
      : 'ws://localhost:8000/ws');
    this.url = url || this.defaultUrl;
    this.debug = !!debug;
    this.ws = null;
  }

  /**
   * Tells us whether or not the WebSocket is connected
   * @returns {boolean}
   */
  isConnected() {
    return !!this.ws;
  }

  /**
   * Writes WebSocket logs to console
   * @param  {...any} args
   * @returns {true}
   */
  log(...args) {
    const date = new Date().toISOString();
    const logs = [`[Websocket/${date}]`].concat(args).map((arg) => {
      if (typeof arg === 'object' && arg !== null) {
        return JSON.stringify(arg, null, 2);
      } else {
        return arg;
      }
    });
    if (this.debug) {
      console.log(...logs);
    }
    return true;
  }

  /**
   * Connects to Realtime API Websocket Server
   * @param {{model?: string}} [settings]
   * @returns {Promise<true>}
   */
  async connect({ model } = { model: 'gpt-4o-realtime-preview-2024-10-01' }) {
    if (this.isConnected()) {
      throw new Error(`Already connected`);
    }
    if (globalThis.WebSocket) {
      const WebSocket = globalThis.WebSocket;
      const ws = new WebSocket(this.url);
      ws.addEventListener('message', (event) => {
          try {
              // 原始消息直通
              if (this._rawMessageHandler) {
                  this._rawMessageHandler(event.data);
              }
          } catch (e) {
              console.error('receiveRaw handler error:', e);
          }
          // 兼容原有 JSON 协议
          try {
              const message = JSON.parse(event.data);
              this.receive(message.type, message);
          } catch {
              // 非 JSON 消息，忽略协议分发
          }
      });
      return new Promise((resolve, reject) => {
        const connectionErrorHandler = () => {
          this.disconnect(ws);
          reject(new Error(`Could not connect to "${this.url}"`));
        };
        ws.addEventListener('error', connectionErrorHandler);
        ws.addEventListener('open', () => {
          this.log(`Connected to "${this.url}"`);
          ws.removeEventListener('error', connectionErrorHandler);
          ws.addEventListener('error', () => {
            this.disconnect(ws);
            this.log(`Error, disconnected from "${this.url}"`);
            this.dispatch('close', { error: true });
          });
          ws.addEventListener('close', () => {
            this.disconnect(ws);
            this.log(`Disconnected from "${this.url}"`);
            this.dispatch('close', { error: false });
          });
          this.ws = ws;
          resolve(true);
        });
      });
    } else {
      /**
       * Node.js
       */
      const moduleName = 'ws';
      const wsModule = await import(/* webpackIgnore: true */ moduleName);
      const WebSocket = wsModule.default;
      const ws = new WebSocket(this.url);
      ws.on('message', (data) => {
          try {
              // 原始消息直通
              if (this._rawMessageHandler) {
                  this._rawMessageHandler(data);
              }
          } catch (e) {
              console.error('receiveRaw handler error:', e);
          }
          // 兼容原有 JSON 协议
          try {
              const message = JSON.parse(data.toString());
              this.receive(message.type, message);
          } catch {
              // 非 JSON 消息，忽略协议分发
          }

      });
      return new Promise((resolve, reject) => {
        const connectionErrorHandler = () => {
          this.disconnect(ws);
          reject(new Error(`Could not connect to "${this.url}"`));
        };
        ws.on('error', connectionErrorHandler);
        ws.on('open', () => {
          this.log(`Connected to "${this.url}"`);
          ws.removeListener('error', connectionErrorHandler);
          ws.on('error', () => {
            this.disconnect(ws);
            this.log(`Error, disconnected from "${this.url}"`);
            this.dispatch('close', { error: true });
          });
          ws.on('close', () => {
            this.disconnect(ws);
            this.log(`Disconnected from "${this.url}"`);
            this.dispatch('close', { error: false });
          });
          this.ws = ws;
          resolve(true);
        });
      });
    }
  }

  /**
   * Disconnects from Realtime API server
   * @param {WebSocket} [ws]
   * @returns {true}
   */
  disconnect(ws) {
    if (!ws || this.ws === ws) {
      this.ws && this.ws.close();
      this.ws = null;
      return true;
    }
  }

  /**
   * Receives an event from WebSocket and dispatches as "server.{eventName}" and "server.*" events
   * @param {string} eventName
   * @param {{[key: string]: any}} event
   * @returns {true}
   */
  receive(eventName, event) {
    this.log(`received:`, eventName, event);
    this.dispatch(`server.${eventName}`, event);
    this.dispatch('server.*', event);
    return true;
  }

    /**
     * Register a raw message handler to receive original WebSocket frames
     * Pass null to remove the handler
     * @param {(data: any) => void|null} handler
     * @returns {true}
     */
    receiveRaw(handler) {
        if (handler !== null && typeof handler !== 'function') {
            throw new Error('handler must be a function or null');
        }
        this._rawMessageHandler = handler;
        return true;
    }


    /**
   * Sends an event to WebSocket and dispatches as "client.{eventName}" and "client.*" events
   * @param {string} eventName
   * @param {{[key: string]: any}} event
   * @returns {true}
   */
  send(eventName, data) {
    if (!this.isConnected()) {
      throw new Error(`RealtimeAPI is not connected`);
    }
    data = data || {};
    if (typeof data !== 'object') {
      throw new Error(`data must be an object`);
    }
    const event = {
      event_id: RealtimeUtils.generateId('evt_'),
      type: eventName,
      ...data,
    };
    this.dispatch(`client.${eventName}`, event);
    this.dispatch('client.*', event);
    this.log(`sent:`, eventName, event);
    this.ws.send(JSON.stringify(event));
    return true;
  }

    /**
     * Send raw data over WebSocket without any wrapping or JSON encoding
     * @param {string|ArrayBuffer|Blob|Buffer|TypedArray|DataView} data
     * @returns {true}
     */
    sendRaw(data) {
        if (!this.isConnected()) {
            throw new Error('RealtimeAPI is not connected');
        }
        try {
            const isBinary =
                data instanceof ArrayBuffer ||
                ArrayBuffer.isView(data) ||
                (typeof Blob !== 'undefined' && data instanceof Blob);
            this.log(
                `sent(raw):`,
                isBinary ? `[binary ${data.byteLength ?? data.size ?? 'unknown'} bytes]` : data,
            );
        } catch {
            // 安全起见，不阻塞发送
        }
        this.ws.send(data);
        return true;
    }

}
