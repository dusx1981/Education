/**
 * UI交互模块
 */

class UIManager {
    constructor(chatManager) {
        this.chatManager = chatManager;
    }

    /**
     * 初始化事件监听器
     */
    initEventListeners() {
        const input = document.getElementById('messageInput');
        const sendButton = document.getElementById('sendButton');
        
        if (!input || !sendButton) {
            console.error('UI元素未找到');
            return;
        }
        
        // 回车发送消息
        input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.chatManager.sendMessage();
            }
        });
        
        // 输入框获取焦点时滚动到底部
        input.addEventListener('focus', () => {
            Utils.scrollToBottom(document.getElementById('chatMessages'));
        });
        
        // 按钮点击发送消息
        sendButton.addEventListener('click', () => {
            this.chatManager.sendMessage();
        });
        
        // 自动聚焦输入框
        setTimeout(() => {
            input.focus();
        }, 500);
        
        // 窗口调整大小时重新计算布局
        window.addEventListener('resize', this.handleResize.bind(this));
    }

    /**
     * 处理窗口调整大小
     */
    handleResize() {
        // 这里可以添加响应式布局的调整逻辑
        console.log('窗口大小改变，重新调整布局');
        
        // 确保聊天区域滚动到底部
        Utils.scrollToBottom(document.getElementById('chatMessages'));
    }

    /**
     * 更新侧边栏内容
     * @param {Object} data - 要更新的数据
     */
    updateSidebar(data) {
        if (data.achievements) {
            this.updateAchievements(data.achievements);
        }
        
        if (data.grammarPoints) {
            this.updateGrammarPoints(data.grammarPoints);
        }
        
        if (data.progress) {
            this.updateProgressBar(data.progress);
        }
    }

    /**
     * 更新成就墙
     * @param {Array} achievements - 成就列表
     */
    updateAchievements(achievements) {
        const achievementsContainer = document.getElementById('achievements');
        if (!achievementsContainer) return;
        
        achievementsContainer.innerHTML = '';
        achievements.forEach(achievement => {
            const div = document.createElement('div');
            div.className = 'achievement';
            div.textContent = achievement;
            achievementsContainer.appendChild(div);
        });
    }

    /**
     * 更新语法知识点
     * @param {Array} grammarPoints - 语法点列表
     */
    updateGrammarPoints(grammarPoints) {
        const grammarContainer = document.getElementById('grammarPoints');
        if (!grammarContainer) return;
        
        grammarContainer.innerHTML = '';
        grammarPoints.forEach(point => {
            const div = document.createElement('div');
            div.textContent = point;
            grammarContainer.appendChild(div);
        });
    }

    /**
     * 更新进度条
     * @param {number} progress - 进度百分比 (0-100)
     */
    updateProgressBar(progress) {
        const progressFill = document.querySelector('.progress-fill');
        if (progressFill) {
            progressFill.style.width = `${Math.min(progress, 100)}%`;
        }
    }

    /**
     * 显示加载状态
     * @param {boolean} show - 是否显示
     */
    showLoading(show) {
        const loadingElement = document.getElementById('loadingIndicator');
        if (!loadingElement) return;
        
        loadingElement.style.display = show ? 'block' : 'none';
    }

    /**
     * 显示错误信息
     * @param {string} message - 错误消息
     * @param {boolean} isFatal - 是否是致命错误
     */
    showError(message, isFatal = false) {
        const errorElement = document.createElement('div');
        errorElement.className = `error-message ${isFatal ? 'fatal' : 'warning'}`;
        errorElement.innerHTML = `
            <div class="error-icon">${isFatal ? '❌' : '⚠️'}</div>
            <div class="error-text">${Utils.escapeHtml(message)}</div>
            ${!isFatal ? '<button class="error-dismiss">×</button>' : ''}
        `;
        
        errorElement.style.cssText = `
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.3);
            z-index: 10001;
            display: flex;
            align-items: center;
            gap: 15px;
            max-width: 400px;
        `;
        
        document.body.appendChild(errorElement);
        
        // 添加关闭按钮事件
        if (!isFatal) {
            const dismissBtn = errorElement.querySelector('.error-dismiss');
            dismissBtn.addEventListener('click', () => {
                document.body.removeChild(errorElement);
            });
            
            // 5秒后自动消失
            setTimeout(() => {
                if (document.body.contains(errorElement)) {
                    document.body.removeChild(errorElement);
                }
            }, 5000);
        }
    }
}

// 导出UI管理器
window.UIManager = UIManager;