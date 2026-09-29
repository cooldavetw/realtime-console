import { useEffect, useRef, useCallback, useState } from 'react'
import { RealtimeClient } from '../lib/client.js'
import { ItemType } from '../lib/client.js'
import { WavRecorder, WavStreamPlayer } from '../lib/wavtools/index.js'
import { WavRenderer } from '../utils/wav_renderer'

import { X, Edit, Zap, ArrowUp, ArrowDown, Book, Search, Code } from 'react-feather'
import { Button } from '../components/button/Button'
import { Toggle } from '../components/toggle/Toggle'

import './ConsolePage.scss'
import { isJsxOpeningLikeElement } from 'typescript'
import { RealtimeUtils } from '../lib/utils'

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
        new RealtimeClient()
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

        if (client.getTurnDetectionType() === 'vad') {
            await wavRecorder.record((data) => client.appendInputAudio(data.mono))
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

    /**
     * 删除对话项
     */
    const deleteConversationItem = useCallback(async (id: string) => {
        const client = clientRef.current
        if (client.conversation.deleteItem(id)) {
            // 删除成功，更新 UI
            setItems(client.conversation.getItems())
        }
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
        await wavRecorder.record((data) => client.appendInputAudio(data.mono))
    }

    /**
     * In push-to-talk mode, stop recording
     */
    const stopRecording = async () => {
        setIsRecording(false)
        const client = clientRef.current
        const wavRecorder = wavRecorderRef.current
        await wavRecorder.pause()
        client.createResponse()
    }

    /**
     * Switch between Manual <> VAD mode for communication
     */
    const changeTurnEndType = async (value: string) => {
        const client = clientRef.current
        const wavRecorder = wavRecorderRef.current
        const wavStreamPlayer = wavStreamPlayerRef.current
        await wavStreamPlayer.interrupt()

        if (value === 'none' && wavRecorder.getStatus() === 'recording') {
            await wavRecorder.pause()
        }

        // 使用新的 updateSession 方法更新会话配置
        await client.updateSession({
            mode: value === 'none' ? 'push_to_talk' : 'vad'
        })

        if (value === 'vad' && client.isConnected()) {
            await wavRecorder.record((data) => client.appendInputAudio(data.mono))
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
        const client = clientRef.current

        // handle realtime events from client + server for event logging
        client.on('realtime.event', (realtimeEvent: RealtimeEvent) => {
            setRealtimeEvents((realtimeEvents) => {
                const lastEvent = realtimeEvents[realtimeEvents.length - 1]
                if (lastEvent?.event.type === realtimeEvent.event.type) {
                    // if we receive multiple events in a row, aggregate them for display purposes
                    lastEvent.count = (lastEvent.count || 0) + 1
                    return realtimeEvents.slice(0, -1).concat(lastEvent)
                } else {
                    return realtimeEvents.concat(realtimeEvent)
                }
            })
        })
        client.on('error', (event: any) => console.error(event))


        // 处理会话创建事件
        client.on('session.created', (event: any) => {
            console.log('Session created:', event)
        })

        // 处理会话更新事件
        client.on('session.updated', (event: any) => {
            console.log('Session updated:', event)
        })

        // VAD事件
        client.on('vad.speech_started', () => {
            console.log('Speech started')
            wavStreamPlayer.interrupt()
        })
        client.on('vad.speech_stopped', () => {
            console.log('Speech stopped')
        })
        // 转录事件
        client.on('transcript.created', (event: any) => {
            console.log('Transcript created:', event)
            // 更新界面
            setItems(client.conversation.getItems())
        })

        // 查询事件
        client.on('query.sent', (event: any) => {
            console.log('Query sent:', event)
            setItems(client.conversation.getItems())
        })

        // 响应事件
        client.on('response.created', (event: any) => {
            console.log('Response created:', event)
            setItems(client.conversation.getItems())
        })

        client.on('response.cancelled', (event: any) => {
            console.log('Response cancelled:', event)
            setItems(client.conversation.getItems())
        })

        client.on('conversation.interrupted', async () => {
            console.log('Conversation interrupted:', event)
            // 中断音频播放
            const trackSampleOffset = await wavStreamPlayer.interrupt()
            // 更新 UI 显示
            setItems(client.conversation.getItems())

        })

        client.on("response.created", async (event: any) => {
            console.log('Response created:', event)
            if (event.audio) {
                // 播放助手的音频回复
                const audioData = event.audio
                    ? event.audio instanceof Int16Array
                        ? event.audio
                        : new Int16Array(RealtimeUtils.base64ToArrayBuffer(event.audio))
                    : new Int16Array(0)
                wavStreamPlayer.add16BitPCM(audioData, event.response_id)
            }
        })

        // 处理对话更新事件
        client.on('conversation.updated', async (event: any) => {
            console.log('Conversation updated:', event)
            const { item, delta } = event

            // 更新 UI 显示
            setItems(client.conversation.getItems())
        })


        // 处理转录创建事件
        client.on('transcript.created', (event: any) => {
            console.log('Transcript created:', event)
            // 更新 UI
            setItems(client.conversation.getItems())
        })

        // 处理响应创建事件
        client.on('response.created', (event: any) => {
            console.log('Response created:', event)
            // 更新 UI
            setItems(client.conversation.getItems())
        })

        // 处理音频开始事件
        client.on('audio.started', (event: any) => {
            console.log('Audio started:', event)
        })

        // 处理音频完成事件
        client.on('audio.completed', (event: any) => {
            console.log('Audio completed:', event)
            // 更新 UI
            setItems(client.conversation.getItems())
        })

        return () => {
            // cleanup; resets to defaults
            client.reset()
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
                                    <div className={`conversation-item ${conversationItem.status || ''}`} key={conversationItem.id}>
                                        <div className={`speaker ${conversationItem.role || ''}`}>
                                            <div>
                                                {conversationItem.role === 'user' ? '用户' : '助手'}
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
                                            {/* 根据角色和类型显示不同内容 */}
                                            {conversationItem.role === 'user' && (
                                                <div>
                                                    {conversationItem.formatted?.transcript ||
                                                        conversationItem.content?.transcript ||
                                                        conversationItem.formatted?.text ||
                                                        conversationItem.content?.text ||
                                                        (conversationItem.formatted?.audio?.length ? '(转录中...)' : '(发送中...)')}
                                                </div>
                                            )}

                                            {conversationItem.role === 'assistant' && (
                                                <div>
                                                    {conversationItem.formatted?.text ||
                                                        conversationItem.content?.text ||
                                                        (conversationItem.status === 'interrupted' ? '(已中断)' : '(生成中...)')}
                                                </div>
                                            )}

                                            {/* 显示音频播放器 */}
                                            {conversationItem.formatted?.file && (
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
                        {isConnected && (
                            <Toggle
                                defaultValue={false}
                                labels={['manual', 'vad']}
                                values={['none', 'vad']}
                                onChange={(_, value) => changeTurnEndType(value)}
                            />
                        )}
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
