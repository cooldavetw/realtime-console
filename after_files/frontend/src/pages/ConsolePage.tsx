/**
 * Change this if you want to connect to a local relay server!
 * This will require you to set OPENAI_API_KEY= in a `.env` file
 * You can run it with `npm run relay`, in parallel with `npm start`
 *
 * Simply switch the lines by commenting one and removing the other
 */
// Flowise Base URL
const FLOWISE_BASE_URL = process.env.REACT_APP_FLOWISE_BASE_URL
// Flowise API Key
const FLOWISE_API_KEY = process.env.REACT_APP_FLOWISE_API_KEY

const OPENAI_API_KEY = process.env.REACT_APP_OPENAI_API_KEY

import { useEffect, useRef, useCallback, useState } from 'react'

import ReactMarkdown from 'react-markdown'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { okaidia } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { RealtimeClient } from '../lib/client.js'
import { ItemType } from '../lib/client.js'
import { WavRecorder, WavStreamPlayer } from '../lib/wavtools/index.js'
import { instructions } from '../utils/transcription_config'
import { WavRenderer } from '../utils/wav_renderer'

import { X, Edit, Zap, ArrowUp, ArrowDown, Book, Search, Code } from 'react-feather'
import { Button } from '../components/button/Button'
import { Toggle } from '../components/toggle/Toggle'

import './ConsolePage.scss'
import { isJsxOpeningLikeElement } from 'typescript'

/**
 * Type for result from get_weather() function call
 */
interface Coordinates {
    lat: number;
    lng: number;
    location?: string;
    temperature?: {
        value: number;
        units: string;
    };
    wind_speed?: {
        value: number;
        units: string;
    };
}

interface ToolMessage {
    type: string
    content: string
    artifacts?: any
    sources?: any
}

interface Tool {
    name: string;
    description: string;
    parameters?: {
        type: string,
        properties: Record<string, any>,
        required: string[]
    },
    messages?: ToolMessage[]
}

/**
 * Type for all event logs
 */
interface RealtimeEvent {
    time: string;
    source: 'client' | 'server';
    count?: number;
    event: { [key: string]: any };
}

export function ConsolePage() {
    /**
     * Ask user for API Key
     * If we're using the local relay server, we don't need this
     */
    const apiKey = ''

    /**
     * Instantiate:
     * - WavRecorder (speech input)
     * - WavStreamPlayer (speech output)
     * - RealtimeClient (API client)
     */
    const wavRecorderRef = useRef<WavRecorder>(
        new WavRecorder({ sampleRate: 24000 })
    )
    const wavStreamPlayerRef = useRef<WavStreamPlayer>(
        new WavStreamPlayer({ sampleRate: 24000 })
    )
    const clientRef = useRef<RealtimeClient>(
        new RealtimeClient({
                apiKey: apiKey ,
                dangerouslyAllowAPIKeyInBrowser: true
            }
        )
    )

    const sessionID = 'session-' + Date.now()
    /**
     * References for
     * - Rendering audio visualization (canvas)
     * - Autoscrolling event logs
     * - Timing delta for event log displays
     */
    const clientCanvasRef = useRef<HTMLCanvasElement>(null)
    const serverCanvasRef = useRef<HTMLCanvasElement>(null)
    const eventsScrollHeightRef = useRef(0)
    const eventsScrollRef = useRef<HTMLDivElement>(null)
    const startTimeRef = useRef<string>(new Date().toISOString())

    /**
     * All of our variables for displaying application state
     * - items are all conversation items (dialog)
     * - realtimeEvents are event logs, which can be expanded
     * - memoryKv is for set_memory() function
     * - coords, marker are for get_weather() function
     */
    const [items, setItems] = useState<ItemType[]>([])
    const [realtimeEvents, setRealtimeEvents] = useState<RealtimeEvent[]>([])
    const [expandedEvents, setExpandedEvents] = useState<{
        [key: string]: boolean;
    }>({})
    const [isConnected, setIsConnected] = useState(false)
    const [canPushToTalk, setCanPushToTalk] = useState(true)
    const [isRecording, setIsRecording] = useState(false)
    const [memoryKv, setMemoryKv] = useState<{ [key: string]: any }>({})
    const [coords, setCoords] = useState<Coordinates | null>({
        lat: 37.775593,
        lng: -122.418137
    })
    const [marker, setMarker] = useState<Coordinates | null>(null)

    const [tools, setTools] = useState<Tool[]>([])
    const [activeTab, setActiveTab] = useState(0) // To track the active tab
    /**
     * Utility for formatting the timing of logs
     */
    const formatTime = useCallback((timestamp: string) => {
        const startTime = startTimeRef.current
        const t0 = new Date(startTime).valueOf()
        const t1 = new Date(timestamp).valueOf()
        const delta = t1 - t0
        const hs = Math.floor(delta / 10) % 100
        const s = Math.floor(delta / 1000) % 60
        const m = Math.floor(delta / 60_000) % 60
        const pad = (n: number) => {
            let s = n + ''
            while (s.length < 2) {
                s = '0' + s
            }
            return s
        }
        return `${pad(m)}:${pad(s)}.${pad(hs)}`
    }, [])

    /**
     * Connect to conversation:
     * WavRecorder taks speech input, WavStreamPlayer output, client is API client
     */
    const connectConversation = useCallback(async () => {
        const client = clientRef.current
        const wavRecorder = wavRecorderRef.current
        const wavStreamPlayer = wavStreamPlayerRef.current

        // Set state variables
        startTimeRef.current = new Date().toISOString()
        setIsConnected(true)
        setRealtimeEvents([])
        setItems(client.conversation.getItems())

        // Connect to microphone
        await wavRecorder.begin()

        // Connect to audio output
        await wavStreamPlayer.connect()

        // Connect to realtime API
        await client.connect()

        // 注册原始消息处理器，用于接收服务器发送的响应（尤其是音频数据）
        client.realtime.receiveRaw((data) => {
            console.log("Raw message received:", typeof data);
            if (typeof data === "string") {
                try {
                    // 尝试解析为 JSON
                    const jsonData = JSON.parse(data);
                    console.log("Received JSON data:", jsonData);
                } catch {
                    // 如果不是 JSON，可能是 base64 编码的音频或其他文本消息
                    if (data.startsWith("ERROR:")) {
                        console.error("Server error:", data);
                    } else if (data.length > 100) {
                        // 可能是 base64 编码的音频
                        console.log(`Received base64 data (${data.length} chars)`);
                        try {
                            // 解码为音频并播放
                            const binaryData = Uint8Array.from(atob(data), c => c.charCodeAt(0));
                            const audioBlob = new Blob([binaryData], { type: 'audio/mp3' });
                            const audioUrl = URL.createObjectURL(audioBlob);

                            // 创建音频元素播放
                            const audio = new Audio();
                            audio.src = audioUrl;
                            audio.play().catch(e => console.error("Failed to play audio:", e));
                        } catch (e) {
                            console.error("Failed to process base64 data:", e);
                        }
                    } else {
                        console.log("Received text message:", data);
                    }
                }
            } else if (data instanceof ArrayBuffer) {
                // 二进制数据，可能是音频
                wavStreamPlayer.add16BitPCM(data)
                console.log(`Received binary data: ${data.byteLength} bytes`);
            } else {
                console.log("Received unknown data type:", typeof data);
            }
        });


        if (client.getTurnDetectionType() === 'server_vad') {
            //await wavRecorder.record((data) => client.appendInputAudio(data.mono))
        }
    }, [])

    /**
     * Disconnect and reset conversation state
     */
    const disconnectConversation = useCallback(async () => {
        setIsConnected(false)
        setRealtimeEvents([])
        setItems([])
        setMemoryKv({})
        setCoords({
            lat: 37.775593,
            lng: -122.418137
        })
        setMarker(null)

        const client = clientRef.current
        client.disconnect()

        const wavRecorder = wavRecorderRef.current
        await wavRecorder.end()

        const wavStreamPlayer = wavStreamPlayerRef.current
        await wavStreamPlayer.interrupt()
    }, [])

    const deleteConversationItem = useCallback(async (id: string) => {
        const client = clientRef.current
        client.deleteItem(id)
    }, [])

    /**
     * In push-to-talk mode, start recording
     * .appendInputAudio() for each sample
     */
    const startRecording = async () => {
        setIsRecording(true)
        const client = clientRef.current
        const wavRecorder = wavRecorderRef.current
        const wavStreamPlayer = wavStreamPlayerRef.current
        const trackSampleOffset = await wavStreamPlayer.interrupt()
        if (trackSampleOffset?.trackId) {
            const { trackId, offset } = trackSampleOffset
            await client.cancelResponse(trackId, offset)
        }
        await wavRecorder.record((data) => {
            const { mono, raw } = data;
            client.realtime.sendRaw(mono)
        });
    }

    /**
     * In push-to-talk mode, stop recording
     */
    const stopRecording = async () => {
        setIsRecording(false)
        const client = clientRef.current
        const wavRecorder = wavRecorderRef.current
        await wavRecorder.pause()
        const audio = await wavRecorder.save()
        client.realtime.sendRaw('DONE')
        await wavRecorder.clear()
        //client.createResponse()
    }

    /**
     * Switch between Manual <> VAD mode for communication
     */
    const changeTurnEndType = async (value: string) => {
        const client = clientRef.current
        const wavRecorder = wavRecorderRef.current
        if (value === 'none' && wavRecorder.getStatus() === 'recording') {
            await wavRecorder.pause()
        }
        if (value === 'server_vad' && client.isConnected()) {
            //await wavRecorder.record((data) => client.appendInputAudio(data.mono))
        }
        setCanPushToTalk(value === 'none')
    }

    /**
     * Auto-scroll the event logs
     */
    useEffect(() => {
        if (eventsScrollRef.current) {
            const eventsEl = eventsScrollRef.current
            const scrollHeight = eventsEl.scrollHeight
            // Only scroll if height has just changed
            if (scrollHeight !== eventsScrollHeightRef.current) {
                eventsEl.scrollTop = scrollHeight
                eventsScrollHeightRef.current = scrollHeight
            }
        }
    }, [realtimeEvents])

    /**
     * Auto-scroll the conversation logs
     */
    useEffect(() => {
        const conversationEls = [].slice.call(
            document.body.querySelectorAll('[data-conversation-content]')
        )
        for (const el of conversationEls) {
            const conversationEl = el as HTMLDivElement
            conversationEl.scrollTop = conversationEl.scrollHeight
        }
    }, [items])

    /**
     * Set up render loops for the visualization canvas
     */
    useEffect(() => {
        let isLoaded = true

        const wavRecorder = wavRecorderRef.current
        const clientCanvas = clientCanvasRef.current
        let clientCtx: CanvasRenderingContext2D | null = null

        const wavStreamPlayer = wavStreamPlayerRef.current
        const serverCanvas = serverCanvasRef.current
        let serverCtx: CanvasRenderingContext2D | null = null

        const render = () => {
            if (isLoaded) {
                if (clientCanvas) {
                    if (!clientCanvas.width || !clientCanvas.height) {
                        clientCanvas.width = clientCanvas.offsetWidth
                        clientCanvas.height = clientCanvas.offsetHeight
                    }
                    clientCtx = clientCtx || clientCanvas.getContext('2d')
                    if (clientCtx) {
                        clientCtx.clearRect(0, 0, clientCanvas.width, clientCanvas.height)
                        const result = wavRecorder.recording
                            ? wavRecorder.getFrequencies('voice')
                            : { values: new Float32Array([0]) }
                        WavRenderer.drawBars(
                            clientCanvas,
                            clientCtx,
                            result.values,
                            '#0099ff',
                            10,
                            0,
                            8
                        )
                    }
                }
                if (serverCanvas) {
                    if (!serverCanvas.width || !serverCanvas.height) {
                        serverCanvas.width = serverCanvas.offsetWidth
                        serverCanvas.height = serverCanvas.offsetHeight
                    }
                    serverCtx = serverCtx || serverCanvas.getContext('2d')
                    if (serverCtx) {
                        serverCtx.clearRect(0, 0, serverCanvas.width, serverCanvas.height)
                        const result = wavStreamPlayer.analyser
                            ? wavStreamPlayer.getFrequencies('voice')
                            : { values: new Float32Array([0]) }
                        WavRenderer.drawBars(
                            serverCanvas,
                            serverCtx,
                            result.values,
                            '#009900',
                            10,
                            0,
                            8
                        )
                    }
                }
                window.requestAnimationFrame(render)
            }
        }
        render()

        return () => {
            isLoaded = false
        }
    }, [])

    /**
     * Core RealtimeClient and audio capture setup
     * Set all of our instructions, tools, events and more
     */
    useEffect(() => {
        // Get refs
        const wavStreamPlayer = wavStreamPlayerRef.current

        return () => {
            // cleanup; resets to defaults
        }
    }, [])

    /**
     * Render the application
     */
    return (
        <div data-component="ConsolePage">
            <div className="content-top">
                <div className="content-title">
                    <img src={`${process.env.PUBLIC_URL}/segma.svg`} />
                    <span>realtime console</span>
                </div>
            </div>
            <div className="content-main">
                <div className="content-logs">
                    <div className="content-block events">
                        <div className="visualization">
                            <div className="visualization-entry client">
                                <canvas ref={clientCanvasRef} />
                            </div>
                            <div className="visualization-entry server">
                                <canvas ref={serverCanvasRef} />
                            </div>
                        </div>
                        <div className="content-block-title">events</div>
                        <div className="content-block-body" ref={eventsScrollRef}>
                            {!realtimeEvents.length && `awaiting connection...`}
                            {realtimeEvents.map((realtimeEvent, i) => {
                                const count = realtimeEvent.count
                                const event = { ...realtimeEvent.event }
                                if (event.type === 'input_audio_buffer.append') {
                                    event.audio = `[trimmed: ${event.audio.length} bytes]`
                                } else if (event.type === 'response.audio.delta') {
                                    event.delta = `[trimmed: ${event.delta.length} bytes]`
                                }
                                return (
                                    <div className="event" key={event.event_id}>
                                        <div className="event-timestamp">
                                            {formatTime(realtimeEvent.time)}
                                        </div>
                                        <div className="event-details">
                                            <div
                                                className="event-summary"
                                                onClick={() => {
                                                    // toggle event details
                                                    const id = event.event_id
                                                    const expanded = { ...expandedEvents }
                                                    if (expanded[id]) {
                                                        delete expanded[id]
                                                    } else {
                                                        expanded[id] = true
                                                    }
                                                    setExpandedEvents(expanded)
                                                }}
                                            >
                                                <div
                                                    className={`event-source ${
                                                        event.type === 'error'
                                                            ? 'error'
                                                            : realtimeEvent.source
                                                    }`}
                                                >
                                                    {realtimeEvent.source === 'client' ? (
                                                        <ArrowUp />
                                                    ) : (
                                                        <ArrowDown />
                                                    )}
                                                    <span>
                            {event.type === 'error'
                                ? 'error!'
                                : realtimeEvent.source}
                          </span>
                                                </div>
                                                <div className="event-type">
                                                    {event.type}
                                                    {count && ` (${count})`}
                                                </div>
                                            </div>
                                            {!!expandedEvents[event.event_id] && (
                                                <div className="event-payload">
                                                    {JSON.stringify(event, null, 2)}
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                )
                            })}
                        </div>
                    </div>
                    <div className="content-block conversation">
                        <div className="content-block-title">conversation</div>
                        <div className="content-block-body" data-conversation-content>
                            {!items.length && `awaiting connection...`}
                            {items.map((conversationItem, i) => {
                                return (
                                    <div className="conversation-item" key={conversationItem.id}>
                                        <div className={`speaker ${conversationItem.role || ''}`}>
                                            <div>
                                                {(
                                                    conversationItem.role || conversationItem.type
                                                ).replaceAll('_', ' ')}
                                            </div>
                                            <div
                                                className="close"
                                                onClick={() =>
                                                    deleteConversationItem(conversationItem.id)
                                                }
                                            >
                                                <X />
                                            </div>
                                        </div>
                                        <div className={`speaker-content`}>
                                            {/* tool response */}
                                            {conversationItem.type === 'function_call_output' && (
                                                <div>{conversationItem.formatted.output}</div>
                                            )}
                                            {/* tool call */}
                                            {!!conversationItem.formatted.tool && (
                                                <div>
                                                    {conversationItem.formatted.tool.name}(
                                                    {conversationItem.formatted.tool.arguments})
                                                </div>
                                            )}
                                            {!conversationItem.formatted.tool &&
                                                conversationItem.role === 'user' && (
                                                    <div>
                                                        {conversationItem.formatted.transcript ||
                                                            (conversationItem.formatted.audio?.length
                                                                ? '(awaiting transcript)'
                                                                : conversationItem.formatted.text ||
                                                                '(item sent)')}
                                                    </div>
                                                )}
                                            {!conversationItem.formatted.tool &&
                                                conversationItem.role === 'assistant' && (
                                                    <div>
                                                        {conversationItem.formatted.transcript ||
                                                            conversationItem.formatted.text ||
                                                            '(truncated)'}
                                                    </div>
                                                )}
                                            {conversationItem.formatted.file && (
                                                <audio
                                                    src={conversationItem.formatted.file.url}
                                                    controls
                                                />
                                            )}
                                        </div>
                                    </div>
                                )
                            })}
                        </div>
                    </div>
                    <div className="content-actions">
                        <Toggle
                            defaultValue={false}
                            labels={['manual', 'vad']}
                            values={['none', 'server_vad']}
                            onChange={(_, value) => changeTurnEndType(value)}
                        />
                        <div className="spacer" />
                        {isConnected && canPushToTalk && (
                            <Button
                                label={isRecording ? 'release to send' : 'push to talk'}
                                buttonStyle={isRecording ? 'alert' : 'regular'}
                                disabled={!isConnected || !canPushToTalk}
                                onMouseDown={startRecording}
                                onMouseUp={stopRecording}
                            />
                        )}
                        <div className="spacer" />
                        <Button
                            label={isConnected ? 'disconnect' : 'connect'}
                            iconPosition={isConnected ? 'end' : 'start'}
                            icon={isConnected ? X : Zap}
                            buttonStyle={isConnected ? 'regular' : 'action'}
                            onClick={
                                isConnected ? disconnectConversation : connectConversation
                            }
                        />
                    </div>
                </div>
            </div>
        </div>
    )
}
