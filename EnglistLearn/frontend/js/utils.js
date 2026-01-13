/**
 * 工具函数集合
 */

class Utils {
    /**
     * 获取当前时间格式化字符串
     * @returns {string} HH:MM 格式的时间
     */
    static getCurrentTime() {
        const now = new Date();
        return now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    /**
     * HTML转义
     * @param {string} text - 要转义的文本
     * @returns {string} 转义后的文本
     */
    static escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * 正则表达式转义
     * @param {string} string - 要转义的字符串
     * @returns {string} 转义后的字符串
     */
    static escapeRegExp(string) {
        return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }

    /**
     * 格式化消息文本（添加HTML标签、表情等）
     * @param {string} text - 原始文本
     * @returns {string} 格式化后的HTML
     */
    // static formatMessage(text) {
    //     let formatted = text;
        
    //     // 1. 处理表情符号
    //     const emojiMap = {
    //         ':)': '😊',
    //         ':(': '😢',
    //         ':D': '😄',
    //         '<3': '❤️',
    //         '^^': '😊',
    //         ':\\': '😅',
    //         ';)': '😉',
    //         ':P': '😛'
    //     };
        
    //     Object.keys(emojiMap).forEach(key => {
    //         formatted = formatted.replace(new RegExp(this.escapeRegExp(key), 'g'), emojiMap[key]);
    //     });
        
    //     // 2. 处理Markdown
    //     formatted = formatted.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    //     formatted = formatted.replace(/\*([^*]+)\*/g, '<em>$1</em>');
        
    //     // 3. 处理换行
    //     formatted = formatted.replace(/\n/g, '<br>');
        
    //     // 4. 高亮英文单词（简单版本）
    //     // 创建一个临时标记来避免高亮HTML标签内的单词
    //     formatted = formatted.replace(/([^<]*)(<[^>]+>)?/g, (match, textPart, tagPart) => {
    //         if (textPart) {
    //             // 在文本部分高亮英文单词
    //             textPart = textPart.replace(/\b([A-Za-z][A-Za-z']{2,})\b/g, (wordMatch, word) => {
    //                 const shortWords = ['the', 'and', 'but', 'for', 'are', 'was', 'were', 'have', 'has', 'had'];
    //                 if (shortWords.includes(word.toLowerCase())) {
    //                     return wordMatch;
    //                 }
    //                 return `<span class="english-word" title="英语单词">${word}</span>`;
    //             });
    //         }
    //         return textPart + (tagPart || '');
    //     });
        
    //     return formatted;
    // }
    static formatMessage(text) {
        let formatted = text;
        
        // 1. 解码HTML实体（首先处理）
        formatted = formatted
            .replace(/&quot;/g, '"')
            .replace(/&amp;/g, '&')
            .replace(/&lt;/g, '<')
            .replace(/&gt;/g, '>')
            .replace(/&#39;/g, "'")
            .replace(/&nbsp;/g, ' ');
        
        // 2. 处理表情符号
        const emojiMap = {
            ':)': '😊',
            ':(': '😢',
            ':D': '😄',
            '<3': '❤️',
            '^^': '😊',
            ':\\': '😅',
            ';)': '😉',
            ':P': '😛'
        };
        
        Object.keys(emojiMap).forEach(key => {
            formatted = formatted.replace(new RegExp(this.escapeRegExp(key), 'g'), emojiMap[key]);
        });
        
        // 3. 处理Markdown
        formatted = formatted.replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>');
        formatted = formatted.replace(/\*([^*\n]+)\*/g, '<em>$1</em>');
        
        // 4. 处理换行
        formatted = formatted.replace(/\n/g, '<br>');
        
        // 5. 高亮英文单词 - 避免在HTML标签内高亮
        // 使用split和join方法来保护HTML标签
        const parts = formatted.split(/(<[^>]+>)/);
        for (let i = 0; i < parts.length; i++) {
            // 只处理非HTML标签部分
            if (!parts[i].startsWith('<') || !parts[i].endsWith('>')) {
                parts[i] = parts[i].replace(/\b([A-Za-z][A-Za-z']{2,})\b/g, (match, word) => {
                    const shortWords = ['the', 'and', 'but', 'for', 'are', 'was', 'were', 'have', 'has', 'had'];
                    if (shortWords.includes(word.toLowerCase())) {
                        return match;
                    }
                    return `<span class="english-word" title="英语单词">${word}</span>`;
                });
            }
        }
        
        return parts.join('');
    }

    /**
     * 滚动到元素底部
     * @param {HTMLElement} element - 要滚动的元素
     */
    static scrollToBottom(element) {
        if (element) {
            element.scrollTop = element.scrollHeight;
        }
    }

    /**
     * 显示通知
     * @param {string} message - 通知消息
     * @param {string} type - 通知类型: 'info' | 'success' | 'warning' | 'error'
     * @param {number} duration - 显示时长(毫秒)
     */
    static showNotification(message, type = 'info', duration = 3000) {
        // 创建通知元素
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.textContent = message;
        notification.style.cssText = `
            position: fixed;
            top: 80px;
            right: 20px;
            padding: 12px 20px;
            border-radius: 8px;
            color: white;
            font-weight: bold;
            z-index: 10000;
            animation: slideIn 0.3s ease;
        `;
        
        // 设置颜色
        const colors = {
            info: '#2196F3',
            success: '#4CAF50',
            warning: '#FF9800',
            error: '#f44336'
        };
        
        notification.style.backgroundColor = colors[type] || colors.info;
        
        // 添加到页面
        document.body.appendChild(notification);
        
        // 自动移除
        setTimeout(() => {
            notification.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.parentNode.removeChild(notification);
                }
            }, 300);
        }, duration);
        
        return notification;
    }

    /**
     * 添加CSS样式
     * @param {string} css - CSS样式字符串
     */
    static addStyles(css) {
        const style = document.createElement('style');
        style.textContent = css;
        document.head.appendChild(style);
    }
}

// 添加通知动画样式
Utils.addStyles(`
    @keyframes slideIn {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(100%);
            opacity: 0;
        }
    }
`);

// 导出工具类
window.Utils = Utils;