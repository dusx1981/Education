/**
 * 英语学习应用主入口
 */

class EnglishLearningApp {
    constructor() {
        // 初始化管理器
        this.sessionManager = new SessionManager();
        this.chatManager = new ChatManager(this.sessionManager);
        this.uiManager = new UIManager(this.chatManager);
        
        this.init();
    }
    
    /**
     * 初始化应用
     */
    async init() {
        try {
            // 添加欢迎消息
            this.chatManager.addWelcomeMessage();
            
            // 初始化会话
            await this.sessionManager.startSession();
            
            // 初始化事件监听器
            this.uiManager.initEventListeners();
            
            // 测试连接
            await this.sessionManager.testConnection();
            
            console.log('应用初始化完成');
        } catch (error) {
            console.error('应用初始化失败:', error);
            this.uiManager.showError('应用初始化失败，请刷新页面重试', true);
        }
    }
    
    /**
     * 发送消息（全局函数，供HTML中的onclick使用）
     */
    sendMessage() {
        if (this.chatManager) {
            this.chatManager.sendMessage();
        }
    }
}

// 应用启动
document.addEventListener('DOMContentLoaded', () => {
    // 创建应用实例
    window.app = new EnglishLearningApp();
    
    // 将发送消息函数暴露到全局
    window.sendMessage = () => {
        if (window.app) {
            window.app.sendMessage();
        }
    };
    
    console.log('英语学习应用已启动');
});