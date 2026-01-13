/**
 * 会话管理模块
 */

class SessionManager {
    constructor() {
        this.sessionId = '';
        this.userId = '';
        this.sessionType = '';
        this.retryCount = 0;
        this.maxRetries = 3;
    }

    /**
     * 开始新会话
     * @returns {Promise<void>}
     */
    async startSession() {
        try {
            this.updateConnectionStatus('connecting');
            
            const response = await fetch(window.API_CONFIG.getUrl('START_SESSION'), {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.sessionId = data.session_id;
                this.userId = data.user_id;
                this.sessionType = data.session_type || 'adk';
                
                console.log(`会话已创建: ${this.sessionId} (类型: ${this.sessionType})`);
                
                if (data.warning) {
                    console.warn('会话创建警告:', data.warning);
                    Utils.showNotification(`会话创建警告: ${data.warning}`, 'warning');
                }
                
                this.updateConnectionStatus('connected');
            } else {
                throw new Error(data.error || 'Failed to start session');
            }
        } catch (error) {
            console.error('创建会话失败:', error);
            // 使用本地会话作为备用
            this.sessionId = `local_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
            this.userId = `user_${Math.random().toString(36).substr(2, 9)}`;
            this.sessionType = 'local';
            
            console.log(`创建本地会话作为备用: ${this.sessionId}`);
            this.updateConnectionStatus('connected');
            Utils.showNotification('已创建本地会话（离线模式）', 'info');
        }
    }

    /**
     * 更新连接状态显示
     * @param {string} status - 状态: 'connected' | 'disconnected' | 'connecting'
     */
    updateConnectionStatus(status) {
        const statusElement = document.getElementById('connectionStatus');
        if (!statusElement) return;
        
        statusElement.className = 'connection-status';
        
        switch(status) {
            case 'connected':
                statusElement.textContent = '✓ 已连接';
                statusElement.classList.add('status-connected');
                break;
            case 'disconnected':
                statusElement.textContent = '✗ 连接失败';
                statusElement.classList.add('status-disconnected');
                break;
            case 'connecting':
                statusElement.textContent = '⌛ 连接中...';
                statusElement.classList.add('status-connecting');
                break;
        }
    }

    /**
     * 测试连接
     * @returns {Promise<void>}
     */
    async testConnection() {
        try {
            const response = await fetch(window.API_CONFIG.getUrl('START_SESSION'), {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            });
            
            if (response.ok) {
                this.updateConnectionStatus('connected');
            } else {
                this.updateConnectionStatus('disconnected');
            }
        } catch (error) {
            this.updateConnectionStatus('disconnected');
        }
    }

    /**
     * 重置重试计数
     */
    resetRetryCount() {
        this.retryCount = 0;
    }

    /**
     * 递增重试计数
     * @returns {boolean} 是否超过最大重试次数
     */
    incrementRetryCount() {
        this.retryCount++;
        return this.retryCount >= this.maxRetries;
    }

    /**
     * 获取重试延迟时间（指数退避）
     * @returns {number} 延迟时间(毫秒)
     */
    getRetryDelay() {
        return 1000 * Math.pow(2, this.retryCount);
    }
}

// 导出会话管理器
window.SessionManager = SessionManager;