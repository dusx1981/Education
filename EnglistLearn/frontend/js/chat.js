/**
 * 聊天功能模块
 */

class ChatManager {
    constructor(sessionManager) {
        this.sessionManager = sessionManager;
        this.isStreaming = false;
        this.currentBotMessageId = null;
        this.botMessageContent = '';
        this.streamController = null;
        this.wordsLearned = 0;
    }

    /**
     * 发送消息
     * @returns {Promise<void>}
     */
    async sendMessage() {
        if (this.isStreaming) {
            console.log('正在等待上一个回复完成');
            Utils.showNotification('请等待当前回复完成', 'warning');
            return;
        }
        
        const input = document.getElementById('messageInput');
        const message = input.value.trim();
        const button = document.getElementById('sendButton');
        
        if (!message) {
            Utils.showNotification('请输入消息', 'warning');
            return;
        }
        
        // 添加用户消息到界面
        this.addMessage(message, 'user');
        input.value = '';
        button.disabled = true;
        this.isStreaming = true;
        
        // 显示正在输入指示器
        this.showTyping(true);
        
        try {
            // 取消之前的流（如果有）
            if (this.streamController) {
                this.streamController.abort();
            }
            
            // 创建新的AbortController用于取消请求
            this.streamController = new AbortController();
            
            // 发送消息到后端并接收流式响应
            const response = await fetch(window.API_CONFIG.getUrl('CHAT_STREAM'), {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    message: message,
                    session_id: this.sessionManager.sessionId,
                    user_id: this.sessionManager.userId,
                    session_type: this.sessionManager.sessionType
                }),
                signal: this.streamController.signal
            });
            
            if (!response.ok) {
                throw new Error(`请求失败: ${response.status}`);
            }
            
            // 创建机器人消息
            this.currentBotMessageId = `bot_${Date.now()}`;
            this.botMessageContent = '';
            this.addMessage('', 'bot', this.currentBotMessageId);
            
            // 处理流式响应
            await this.processStreamResponse(response);
            
            this.sessionManager.resetRetryCount();
            
        } catch (error) {
            if (error.name === 'AbortError') {
                console.log('请求被取消');
            } else {
                console.error('发送消息失败:', error);
                
                // 重试逻辑
                if (!this.sessionManager.incrementRetryCount()) {
                    console.log(`重试 ${this.sessionManager.retryCount}/${this.sessionManager.maxRetries}`);
                    setTimeout(() => this.sendMessage(), this.sessionManager.getRetryDelay());
                    return;
                }
                
                this.showTyping(false);
                this.addMessage('抱歉，连接出现了一些问题。请再试一次！', 'bot');
                this.sessionManager.updateConnectionStatus('disconnected');
            }
        } finally {
            button.disabled = false;
            this.isStreaming = false;
            this.streamController = null;
        }
    }

    /**
     * 处理流式响应
     * @param {Response} response - Fetch响应对象
     * @returns {Promise<void>}
     */
    async processStreamResponse(response) {
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        
        try {
            while (true) {
                const { done, value } = await reader.read();
                
                if (done) {
                    break;
                }
                
                // 解码块数据
                const chunk = decoder.decode(value, { stream: true });
                
                // 解析SSE格式
                const lines = chunk.split('\n');
                
                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const dataStr = line.substring(6);
                        if (dataStr.trim()) {
                            try {
                                const data = JSON.parse(dataStr);
                                this.handleStreamEvent(data);
                            } catch (e) {
                                console.error('解析SSE数据失败:', e, '数据:', dataStr);
                            }
                        }
                    }
                }
            }
        } finally {
            reader.releaseLock();
        }
    }

    /**
     * 处理流事件
     * @param {Object} data - 事件数据
     */
    handleStreamEvent(data) {
        switch(data.type || data.event_type) {
            case 'session_update':
                // 更新会话信息
                this.sessionManager.sessionId = data.session_id;
                this.sessionManager.userId = data.user_id;
                this.sessionManager.sessionType = 'simple';
                console.log('会话已更新:', this.sessionManager.sessionId);
                Utils.showNotification('会话已更新', 'info');
                break;
                
            case 'thinking':
                if (data.text) {
                    this.updateBotMessage(data.text + '...');
                }
                break;
                
            case 'message':
            case 'chunk':
                if (data.text) {
                    this.botMessageContent += data.text;
                    this.updateBotMessage(this.botMessageContent);
                    this.showTyping(false);
                }
                break;
                
            case 'complete':
                this.showTyping(false);
                this.isStreaming = false;
                
                if (data.full_response) {
                    this.botMessageContent = data.full_response;
                    this.updateBotMessage(this.botMessageContent);
                    
                    // 更新学习统计
                    if (data.english_words && data.word_count) {
                        this.updateLearningStats(data.english_words, data.word_count);
                    } else {
                        this.updateLearningStats(this.botMessageContent);
                    }
                }
                break;
                
            case 'error':
                this.showTyping(false);
                this.isStreaming = false;
                this.addMessage(`抱歉，发生错误: ${data.error}`, 'bot');
                Utils.showNotification(data.error, 'error');
                break;
        }
    }

    /**
     * 添加消息到界面
     * @param {string} content - 消息内容
     * @param {string} sender - 发送者: 'user' | 'bot'
     * @param {string} id - 消息ID
     * @returns {string} 消息ID
     */
    addMessage(content, sender, id = null) {
        const chatMessages = document.getElementById('chatMessages');
        const messageDiv = document.createElement('div');
        const messageId = id || `${sender}_${Date.now()}`;
        
        messageDiv.className = `message ${sender}-message`;
        messageDiv.id = messageId;
        
        const time = Utils.getCurrentTime();
        
        if (sender === 'bot') {
            messageDiv.innerHTML = `
                <div class="bot-avatar">ET</div>
                <div class="message-bubble">${Utils.formatMessage(content)}</div>
                <div class="message-time">${time}</div>
            `;
        } else {
            messageDiv.innerHTML = `
                <div class="message-bubble">${Utils.escapeHtml(content)}</div>
                <div class="message-time">${time}</div>
            `;
        }
        
        chatMessages.appendChild(messageDiv);
        Utils.scrollToBottom(chatMessages);
        
        return messageId;
    }

    /**
     * 更新机器人消息
     * @param {string} content - 新内容
     */
    updateBotMessage(content) {
        const botMessage = document.getElementById(this.currentBotMessageId);
        if (botMessage) {
            const bubble = botMessage.querySelector('.message-bubble');
            if (bubble) {
                bubble.innerHTML = Utils.formatMessage(content);
            }
            Utils.scrollToBottom(document.getElementById('chatMessages'));
        }
    }

    /**
     * 显示/隐藏正在输入指示器
     * @param {boolean} show - 是否显示
     */
    showTyping(show) {
        const indicator = document.getElementById('typingIndicator');
        if (indicator) {
            indicator.style.display = show ? 'flex' : 'none';
            
            if (show) {
                Utils.scrollToBottom(document.getElementById('chatMessages'));
            }
        }
    }

    /**
     * 更新学习统计
     * @param {string|Array} content - 消息内容或单词列表
     * @param {number} wordCount - 单词数量（可选）
     */
    updateLearningStats(content, wordCount = null) {
        if (wordCount !== null) {
            this.wordsLearned += wordCount;
        } else {
            // 简单统计新单词（实际应用中应该更智能）
            const words = content.match(/\b[A-Za-z]{4,}\b/g) || [];
            const newWords = words.length;
            this.wordsLearned += Math.min(newWords, 5);
        }
        
        document.getElementById('wordsLearned').textContent = this.wordsLearned;
        
        // 更新进度条
        const progress = Math.min(this.wordsLearned * 2, 100);
        const progressFill = document.querySelector('.progress-fill');
        if (progressFill) {
            progressFill.style.width = `${progress}%`;
        }
        
        // 更新成就
        if (this.wordsLearned >= 5) {
            const achievements = document.getElementById('achievements');
            if (achievements && !achievements.querySelector('.achievement-new')) {
                const newAchievement = document.createElement('div');
                newAchievement.className = 'achievement achievement-new';
                newAchievement.textContent = '🎯 累计学习5个单词！';
                achievements.appendChild(newAchievement);
            }
        }
        
        // 如果有新单词，添加到侧边栏
        if (Array.isArray(content) && content.length > 0) {
            this.addNewWordsToSidebar(content);
        }
    }

    /**
     * 添加新单词到侧边栏
     * @param {Array} words - 单词数组
     */
    addNewWordsToSidebar(words) {
        const grammarSection = document.getElementById('grammarPoints');
        if (grammarSection) {
            const newWordsDiv = document.createElement('div');
            newWordsDiv.innerHTML = `
                <div style="margin-top: 10px; padding: 8px; background: #e3f2fd; border-radius: 5px;">
                    <strong>新单词:</strong><br>
                    ${words.slice(0, 5).join(', ')}
                </div>
            `;
            grammarSection.appendChild(newWordsDiv);
        }
    }

    /**
     * 添加欢迎消息
     */
    addWelcomeMessage() {
        const welcomeTime = Utils.getCurrentTime();
        const chatMessages = document.getElementById('chatMessages');
        
        if (chatMessages) {
            chatMessages.innerHTML = `
                <div class="message bot-message">
                    <div class="bot-avatar">ET</div>
                    <div class="message-bubble">
                        <strong>哈喽！我是英语小天才 ET 🤖✨</strong><br><br>
                        欢迎来到趣味英语世界！<br>
                        🎯 我们可以聊任何你感兴趣的话题<br>
                        🎮 我会在对话中教你英语<br>
                        💡 语法和单词会变得超有趣！<br><br>
                        你想聊什么呢？游戏？音乐？还是有趣的经历？
                    </div>
                    <div class="message-time">${welcomeTime}</div>
                </div>
            `;
        }
    }
}

// 导出聊天管理器
window.ChatManager = ChatManager;