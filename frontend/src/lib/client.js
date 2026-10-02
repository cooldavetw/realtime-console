import { RealtimeEventHandler } from './event_handler.js';
import { RealtimeAPI } from './api.js';
import { RealtimeConversation } from './conversation.js';
import { RealtimeUtils } from './utils.js';

/**
 * @typedef {FormattedItemType & BaseItemType} ItemType
 */

/**
 * RealtimeClient Class
 * @class
 */
export class RealtimeClient extends RealtimeEventHandler {
    /**
     * Create a new RealtimeClient instance
     * @param {{ url?: string, debug?: boolean }} [settings]
     */
    constructor({ url, debug } = {}) {
        super();
        this.defaultSessionConfig = {
            mode: 'push_to_talk', // Default mode
            stt_provider: 'openai',
            tts_provider: 'openai',
            vad_config: {
                threshold: 0.5,
                silence_duration_ms: 500,
                prefix_padding_ms: 300,
            },
        };
        this.sessionConfig = { ...this.defaultSessionConfig };
        this.realtime = new RealtimeAPI({ url, debug });
        this.conversation = new RealtimeConversation();
        this.inputAudioBuffer = new Int16Array(0);
        this._addAPIEventHandlers();
        this.sessionCreated = false;
    }

    /**
     * Resets sessionConfig and conversationConfig to default
     * @private
     * @returns {true}
     */
    _resetConfig() {
        this.sessionCreated = false;
        this.sessionConfig = JSON.parse(JSON.stringify(this.defaultSessionConfig));
        this.inputAudioBuffer = new Int16Array(0);
        return true;
    }

    /**
     * Adds event handlers for backend events
     * @private
     */
    _addAPIEventHandlers() {
        // Log all client and server events
        this.realtime.on('client.*', (event) => {
            const realtimeEvent = {
                time: new Date().toISOString(),
                source: 'client',
                event,
            };
            this.dispatch('realtime.event', realtimeEvent);
        });
        this.realtime.on('server.*', (event) => {
            const realtimeEvent = {
                time: new Date().toISOString(),
                source: 'server',
                event,
            };
            this.dispatch('realtime.event', realtimeEvent);
        });

        /** Handle session.created */
        this.realtime.on('server.session.created', () => {
            this.sessionCreated = true;
            this.dispatch('session.created', { config: this.sessionConfig });
        });

        /** Handle session.updated */
        this.realtime.on('server.session.updated', (event) => {
            this.dispatch('session.updated', { config: event.config });
        });

        /** Handle speech events in VAD mode */
        this.realtime.on('server.vad.speech_started', () => {
            this.dispatch('vad.speech_started');
        });
        this.realtime.on('server.vad.speech_stopped', () => {
            this.dispatch('vad.speech_stopped');
        });

        /** Handle audio events */
        this.realtime.on('server.audio.committed', (event) => {
            this.dispatch('audio.committed', event);
        });
        this.realtime.on('server.audio.cleared', () => {
            this.dispatch('audio.cleared');
        });

        /** Handle conversation events */
        this.realtime.on('server.conversation.updated', (event) => {
            this.conversation.processEvent(event);
            this.dispatch('conversation.updated', event);
        })

        this.realtime.on('server.conversation.interrupted', (event) => {
            this.conversation.processEvent(event);
            this.dispatch('conversation.interrupted', event);
        })

        /** Handle transcript events */
        this.realtime.on('server.transcript.created', (event) => {
            this.conversation.processEvent(event);
            this.dispatch('transcript.created', event);
        });

        /** Handle backend query events */
        this.realtime.on('server.query.sent', (event) => {
            this.dispatch('query.sent', event);
        });
        this.realtime.on('server.response.created', (event) => {
            this.conversation.processEvent(event);
            this.dispatch('response.created', event);
        });

        /** Handle audio response events */
        this.realtime.on('server.audio.started', (event) => {
            this.dispatch('audio.started', event);
        });
        this.realtime.on('server.audio.chunk', (event) => {
            this.dispatch('audio.chunk', event);
        });
        this.realtime.on('server.audio.completed', (event) => {
            this.dispatch('audio.completed', event);
        });

        /** Handle errors */
        this.realtime.on('server.error', (event) => {
            console.error(`[Realtime Error]: ${event.message}`);
            this.dispatch('error', event);
        });
    }

    /**
     * Connects to the server and initializes the session
     * @returns {Promise<boolean>}
     */
    async connect() {
        if (this.isConnected()) {
            throw new Error('Already connected to the server. Please disconnect first.');
        }
        this.sessionCreated = false;
        try {
            await this.realtime.connect();
            this.realtime.send('session.create', { config: this.sessionConfig });
            await this.waitForSessionCreated();
        } catch (error) {
            this.disconnect();
            throw error;
        }
        return true;
    }

    /**
     * Waits until the session is created
     * @returns {Promise<boolean>}
     */
    async waitForSessionCreated() {
        const started = Date.now();
        while (!this.sessionCreated) {
            if (!this.isConnected()) {
                throw new Error('Connection closed before the server created a session.');
            }
            if (Date.now() - started >= 15000) {
                throw new Error(`WebSocket connected to "${this.realtime.url}", but the server did not send session.created within 15 seconds.`);
            }
            await new Promise((resolve) => setTimeout(resolve, 100));
        }
        return true;
    }

    /**
     * Disconnects from the server
     */
    disconnect() {
        this.realtime.disconnect();
        this.sessionCreated = false;
        this.conversation.clear();
    }

    /**
     * Checks if the client is connected
     * @returns {boolean}
     */
    isConnected() {
        return this.realtime.isConnected();
    }

    /**
     * Resets the client instance entirely: disconnects and clears active config
     * @returns {true}
     */
    reset() {
        this.disconnect();
        this.clearEventHandlers();
        this.realtime.clearEventHandlers();
        this._resetConfig();
        this._addAPIEventHandlers();
        return true;
    }

    /**
     * Updates session configuration
     * @param {Object} config - 配置对象
     * @returns {Promise<boolean>}
     */
    async updateSession(config = {}) {
        // 更新本地配置
        for (const key in config) {
            this.sessionConfig[key] = config[key];
        }

        // 如果已连接，发送更新事件
        if (this.isConnected()) {
            this.realtime.send('session.update', { config });
        }

        return true;
    }

    /**
     * Marks the end of audio in push-to-talk mode
     */
    endAudio() {
        this.realtime.send('audio.done');
        this.inputAudioBuffer = new Int16Array(0); // Clear the buffer
    }

    /**
     * Clears audio buffer
     */
    clearAudioBuffer() {
        this.realtime.send('audio.clear');
    }

    /**
     * Sends a custom text query to the server
     * @param {string} text
     */
    sendTextQuery(text) {
        this.realtime.send('query.custom', { text });
    }


    /**
     * Cancels the ongoing server generation and truncates ongoing generation, if applicable
     * If no id provided, will simply call `cancel_generation` command
     * @param {string} id The id of the message to cancel
     * @param {number} [sampleCount] The number of samples to truncate past for the ongoing generation
     * @returns {{item: (AssistantItemType | null)}}
     */
    cancelResponse(id, sampleCount = 0) {
        if (!id) {
            this.realtime.send('response.cancel');
            return { item: null };
        } else if (id) {
            const item = this.conversation.getItem(id);
            if (!item) {
                throw new Error(`Could not find item "${id}"`);
            }
            if (item.type !== 'message') {
                throw new Error(`Can only cancelResponse messages with type "message"`);
            } else if (item.role !== 'assistant') {
                throw new Error(
                    `Can only cancelResponse messages with role "assistant"`,
                );
            }
            this.realtime.send('response.cancel');
            const audioIndex = item.content.findIndex((c) => c.type === 'audio');
            if (audioIndex === -1) {
                throw new Error(`Could not find audio on item to cancel`);
            }
            return { item };
        }
    }

    /**
     * Sends audio response generation request
     */
    createResponse() {
        if (this.getTurnDetectionType() === null && this.inputAudioBuffer.byteLength > 0) {
            this.realtime.send('audio.commit');
            this.conversation.queueInputAudio(this.inputAudioBuffer);
            this.inputAudioBuffer = new Int16Array(0);
        }
        this.realtime.send('response.create');
    }

    /**
     * Gets active VAD mode
     * @returns {"push_to_talk"|"vad"}
     */
    getTurnDetectionType() {
        return this.sessionConfig.mode;
    }

    /**
     * Appends user audio to the existing audio buffer
     * @param {Int16Array|ArrayBuffer} arrayBuffer
     * @returns {true}
     */
    appendInputAudio(arrayBuffer) {
        if (arrayBuffer.byteLength > 0) {
            this.realtime.send("audio.chunk", {
                format: "pcm16", // 假设后台支持的音频格式是 PCM16
                data: RealtimeUtils.arrayBufferToBase64(arrayBuffer), // 将音频数据转换为 base64
            });
            this.inputAudioBuffer = RealtimeUtils.mergeInt16Arrays(
                this.inputAudioBuffer,
                arrayBuffer
            );
        }
        return true;
    }


    /**
     * 发送用户消息内容
     * @param {Array} content - 消息内容数组
     */
    sendUserMessageContent(content) {
        this.realtime.send("user.message", { content });
    }

}
