/**
 * 英语学习应用配置文件
 * 只需修改 SERVER_IP 和 SERVER_PORT 即可
 * 
 * 使用方式：
 * 1. 修改 SERVER_IP 为你的后端服务器IP地址
 * 2. 修改 SERVER_PORT 为你的后端服务器端口号
 * 3. 保存文件，刷新页面即可生效
 */

// ================= 只需修改下面两行 =================
const SERVER_IP = 'localhost';      // 改为你的后端服务器IP地址
const SERVER_PORT = '8000';         // 改为你的后端服务器端口号
// =================================================

// 自动构建基础URL
const BASE_URL = `http://${SERVER_IP}:${SERVER_PORT}`;

// API配置
const API_CONFIG = {
    BASE_URL: BASE_URL,
    ENDPOINTS: {
        // 会话管理
        START_SESSION: '/api/start_session',
        GET_SESSION: (session_id) => `/api/session/${session_id}`,
        
        // 聊天功能
        CHAT_STREAM: '/api/chat/stream',
        CHAT_DIRECT: '/api/chat/direct',
        
        // 系统功能
        HEALTH_CHECK: '/health',
        TEST: '/api/test',
        STATS: '/api/stats'
    },
    
    // 构建完整URL（内部使用）
    _buildUrl: function(endpoint) {
        return this.BASE_URL + endpoint;
    },
    
    // 获取完整的API URL（公开方法）
    getUrl: function(endpointKey, ...params) {
        const endpoint = this.ENDPOINTS[endpointKey];
        if (typeof endpoint === 'function') {
            return this._buildUrl(endpoint(...params));
        }
        return this._buildUrl(endpoint);
    },
    
    // 健康检查
    checkHealth: async function() {
        try {
            const response = await fetch(this.getUrl('HEALTH_CHECK'), {
                method: 'GET',
                timeout: 5000
            });
            return {
                success: response.ok,
                status: response.status,
                url: this.BASE_URL
            };
        } catch (error) {
            return {
                success: false,
                error: error.message,
                url: this.BASE_URL
            };
        }
    },
    
    // 获取配置信息
    getConfigInfo: function() {
        return {
            serverIp: SERVER_IP,
            serverPort: SERVER_PORT,
            baseUrl: BASE_URL,
            configTime: new Date().toISOString()
        };
    }
};

// 全局访问
window.API_CONFIG = API_CONFIG;

// 控制台输出配置信息（开发时查看）
console.log('🎯 后端配置已加载:', API_CONFIG.getConfigInfo());