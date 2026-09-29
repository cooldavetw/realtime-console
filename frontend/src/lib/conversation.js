import { RealtimeUtils } from './utils.js';

/**
 * 对话项内容类型定义
 * @typedef {Object} ItemContentType
 * @property {string} [text] - 文本内容
 * @property {string} [transcript] - 语音转文字内容
 * @property {Int16Array} [audio] - 音频数据
 * @property {string} [audio_id] - 音频ID
 */

/**
 * 对话项类型定义
 * @typedef {Object} ConversationItem
 * @property {string} id - 项目ID
 * @property {string} role - 角色 (user/assistant)
 * @property {string} type - 类型 (text/audio_transcript)
 * @property {ItemContentType} content - 内容
 * @property {string} [status] - 状态 (completed/interrupted)
 * @property {Object} formatted - 格式化后的内容
 * @property {string} [formatted.text] - 格式化的文本
 * @property {string} [formatted.transcript] - 格式化的转录
 * @property {Int16Array} [formatted.audio] - 格式化的音频
 * @property {Object} [formatted.file] - 音频文件
 */

/**
 * RealtimeConversation 类用于管理对话历史和处理对话相关事件
 * @class
 */
export class RealtimeConversation {
    /**
     * 创建一个新的 RealtimeConversation 实例
     */
    constructor() {
        this.clear();
    }

    /**
     * 清除对话历史并重置为默认值
     * @returns {boolean}
     */
    clear() {
        this.items = [];
        this.itemsById = {};
        this.activeResponseId = null;
        return true;
    }

    /**
     * 处理对话更新事件
     * @param {ConversationItem} item - 对话项
     * @returns {ConversationItem}
     */
    updateConversation(item) {
        // 确保有 role 字段
        if (!item.role) {
            console.warn('对话项缺少 role 字段:', item);
            return null;
        }

        // 确保有 type 字段
        if (!item.type) {
            console.warn('对话项缺少 type 字段:', item);
            return null;
        }

        // 标准化格式

        const audioData = item.content?.audio
            ? item.content?.audio instanceof Int16Array
            ? item.content?.audio
            : new Int16Array(RealtimeUtils.base64ToArrayBuffer(item.content?.audio))
            : new Int16Array(0)

        const formattedItem = {
            ...item,
            formatted: {
                text: item.content?.text || '',
                transcript: item.content?.transcript || '',
                audio: audioData
            },
            status: item.status || 'completed'
        };

        // 检查是否已存在
        const existingItem = this.itemsById[item.id];
        if (existingItem) {
            // 更新现有项
            Object.assign(existingItem, formattedItem);

            // 如果有 delta，合并它
            if (item.delta) {
                if (item.delta.text) {
                    existingItem.formatted.text = item.delta.text;
                    if (existingItem.content && existingItem.content.text) {
                        existingItem.content.text = item.delta.text;
                    }
                }

                if (item.delta.transcript) {
                    existingItem.formatted.transcript = item.delta.transcript;
                    if (existingItem.content && existingItem.content.transcript) {
                        existingItem.content.transcript = item.delta.transcript;
                    }
                }

                if (item.delta.audio) {
                    const audioData = item.delta.audio instanceof Int16Array
                        ? item.delta.audio
                        : new Int16Array(RealtimeUtils.base64ToArrayBuffer(item.delta.audio));

                    existingItem.formatted.audio = RealtimeUtils.mergeInt16Arrays(
                        existingItem.formatted.audio,
                        audioData
                    );
                }
            }

            return existingItem;
        } else {
            // 添加新项
            this.items.push(formattedItem);
            this.itemsById[item.id] = formattedItem;
            return formattedItem;
        }
    }

    /**
     * 处理对话中断事件
     * @param {string} responseId - 被中断的响应ID
     * @returns {ConversationItem|null}
     */
    interruptConversation(responseId) {
        if (!responseId) return null;

        const item = this.itemsById[responseId];
        if (item) {
            item.status = 'interrupted';
            return item;
        }

        return null;
    }

    /**
     * 处理事件
     * @param {Object} event - 服务器事件
     * @returns {Object} 处理结果
     */
    processEvent(event) {
        if (!event) return { item: null, delta: null };

        // 处理不同类型的事件
        switch (event.type) {
            case 'transcript.created':
                return this._processTranscriptCreated(event);

            case 'response.created':
                return this._processResponseCreated(event);

            case 'audio.committed':
                return this._processAudioCommitted(event);

            case 'conversation.updated':
                return this._processConversationUpdated(event);

            case 'conversation.interrupted':
                return this._processConversationInterrupted(event);

            default:
                return { item: null, delta: null };
        }
    }

    /**
     * 处理语音转文字完成事件
     * @private
     * @param {Object} event - 事件数据
     * @returns {Object} 处理结果
     */
    _processTranscriptCreated(event) {
        const { audio_id, text } = event;

        // 创建或更新用户输入项
        const item = {
            id: audio_id,
            role: 'user',
            type: 'audio_transcript',
            content: {
                transcript: text,
                audio_id: audio_id
            },
            status: 'completed'
        };

        const updatedItem = this.updateConversation(item);
        return { item: updatedItem, delta: { transcript: text } };
    }

    /**
     * 处理响应创建事件
     * @private
     * @param {Object} event - 事件数据
     * @returns {Object} 处理结果
     */
    _processResponseCreated(event) {
        const { response_id, text, audio } = event;

        // 记录当前活动响应
        this.activeResponseId = response_id;

        const audio_data = audio ? new Int16Array(RealtimeUtils.base64ToArrayBuffer(audio)) : new Int16Array(0)
        // 创建助手回复项
        const item = {
            id: response_id,
            role: 'assistant',
            type: 'text',
            content: { text, audio: audio_data},
            status: 'completed'
        };

        const updatedItem = this.updateConversation(item);
        return { item: updatedItem, delta: { text, audio: audio_data} };
    }

    /**
     * 处理音频提交事件
     * @private
     * @param {Object} event - 事件数据
     * @returns {Object} 处理结果
     */
    _processAudioCommitted(event) {
        const { audio_id } = event;

        // 创建用户音频项
        const item = {
            id: audio_id,
            role: 'user',
            type: 'audio',
            content: { audio_id },
            status: 'processing'
        };

        const updatedItem = this.updateConversation(item);
        return { item: updatedItem, delta: null };
    }

    /**
     * 处理对话更新事件
     * @private
     * @param {Object} event - 事件数据
     * @returns {Object} 处理结果
     */
    _processConversationUpdated(event) {
        const { item, delta } = event;
        delta.audio = delta.audio ? new Int16Array(RealtimeUtils.base64ToArrayBuffer(delta.audio)) : new Int16Array(0)

        const updatedItem = this.updateConversation({
            ...item,
            delta
        });

        return { item: updatedItem, delta };
    }

    /**
     * 处理对话中断事件
     * @private
     * @param {Object} event - 事件数据
     * @returns {Object} 处理结果
     */
    _processConversationInterrupted(event) {
        const { response_id } = event;

        const interruptedItem = this.interruptConversation(response_id);
        this.activeResponseId = null;

        return { item: interruptedItem, delta: null };
    }

    /**
     * 获取所有对话项
     * @returns {ConversationItem[]}
     */
    getItems() {
        console.log('items: ', this.items)
        return this.items.slice();
    }

    /**
     * 获取指定ID的对话项
     * @param {string} id - 对话项ID
     * @returns {ConversationItem|null}
     */
    getItem(id) {
        return this.itemsById[id] || null;
    }

    /**
     * 获取当前活动响应
     * @returns {ConversationItem|null}
     */
    getActiveResponse() {
        return this.activeResponseId ? this.itemsById[this.activeResponseId] : null;
    }

    /**
     * 删除对话项
     * @param {string} id - 要删除的对话项ID
     * @returns {boolean} 删除是否成功
     */
    deleteItem(id) {
        const item = this.itemsById[id];
        if (!item) return false;

        // 从数组中删除
        const index = this.items.findIndex(i => i.id === id);
        if (index !== -1) {
            this.items.splice(index, 1);
        }

        // 从映射中删除
        delete this.itemsById[id];

        // 如果是当前活动响应，重置它
        if (this.activeResponseId === id) {
            this.activeResponseId = null;
        }

        return true;
    }

    /**
     * 添加用户输入文本
     * @param {string} id - 对话项ID
     * @param {string} text - 文本内容
     * @returns {ConversationItem}
     */
    addUserText(id, text) {
        const item = {
            id,
            role: 'user',
            type: 'text',
            content: { text },
            status: 'completed'
        };

        return this.updateConversation(item);
    }

    /**
     * 添加助手回复文本
     * @param {string} id - 对话项ID
     * @param {string} text - 文本内容
     * @returns {ConversationItem}
     */
    addAssistantText(id, text) {
        const item = {
            id,
            role: 'assistant',
            type: 'text',
            content: { text },
            status: 'completed'
        };

        this.activeResponseId = id;
        return this.updateConversation(item);
    }

    /**
     * 缓存音频数据
     * @param {Int16Array} audioData - 音频数据
     */
    queueInputAudio(audioData) {
        this.queuedAudioData = audioData;
        return audioData;
    }
}
