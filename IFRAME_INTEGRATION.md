# 🌐 Dashboard iframe 嵌入指南

## 📋 基本iframe代码

### 方式1: 基本嵌入（本地开发）

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SAP生产延迟预测Dashboard</title>
    <style>
        body {
            margin: 0;
            padding: 0;
            overflow: hidden;
        }
        #dashboard-iframe {
            width: 100%;
            height: 100vh;
            border: none;
        }
    </style>
</head>
<body>
    <iframe 
        id="dashboard-iframe"
        src="http://localhost:8501" 
        title="SAP Production Delay Predictor Dashboard"
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
        allowfullscreen>
    </iframe>
</body>
</html>
```

### 方式2: 响应式嵌入（推荐）

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SAP生产延迟预测Dashboard</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #f5f5f5;
        }
        
        .dashboard-container {
            width: 100%;
            max-width: 1920px;
            margin: 0 auto;
            padding: 20px;
        }
        
        .dashboard-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 10px 10px 0 0;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        
        .dashboard-header h1 {
            margin: 0;
            font-size: 24px;
        }
        
        .dashboard-header p {
            margin: 5px 0 0 0;
            opacity: 0.9;
            font-size: 14px;
        }
        
        .iframe-wrapper {
            position: relative;
            width: 100%;
            height: calc(100vh - 140px);
            background: white;
            border-radius: 0 0 10px 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        
        #dashboard-iframe {
            width: 100%;
            height: 100%;
            border: none;
        }
        
        .loading-overlay {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(255, 255, 255, 0.9);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 1000;
        }
        
        .loading-overlay.hidden {
            display: none;
        }
        
        .spinner {
            border: 4px solid #f3f3f3;
            border-top: 4px solid #667eea;
            border-radius: 50%;
            width: 50px;
            height: 50px;
            animation: spin 1s linear infinite;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        @media (max-width: 768px) {
            .dashboard-container {
                padding: 10px;
            }
            
            .dashboard-header h1 {
                font-size: 18px;
            }
            
            .iframe-wrapper {
                height: calc(100vh - 120px);
            }
        }
    </style>
</head>
<body>
    <div class="dashboard-container">
        <div class="dashboard-header">
            <h1>📊 SAP生产延迟预测Dashboard</h1>
            <p>基于XGBoost的智能预测系统 | 准确率84.8% | 召回率83.8%</p>
        </div>
        
        <div class="iframe-wrapper">
            <div id="loading" class="loading-overlay">
                <div class="spinner"></div>
            </div>
            
            <iframe 
                id="dashboard-iframe"
                src="http://localhost:8501?embed=true" 
                title="SAP Production Delay Predictor Dashboard"
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                allowfullscreen
                onload="hideLoading()">
            </iframe>
        </div>
    </div>
    
    <script>
        function hideLoading() {
            document.getElementById('loading').classList.add('hidden');
        }
        
        // 自动隐藏Streamlit的菜单和页脚
        window.addEventListener('load', function() {
            const iframe = document.getElementById('dashboard-iframe');
            
            // 监听iframe加载完成
            iframe.addEventListener('load', function() {
                try {
                    // 注入CSS隐藏Streamlit默认元素
                    const iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
                    const style = iframeDoc.createElement('style');
                    style.textContent = `
                        #MainMenu {visibility: hidden;}
                        footer {visibility: hidden;}
                        header {visibility: hidden;}
                    `;
                    iframeDoc.head.appendChild(style);
                } catch (e) {
                    console.log('无法访问iframe内容（跨域限制）');
                }
            });
        });
    </script>
</body>
</html>
```

---

## 🌐 **部署到生产环境**

### 方式3: 生产环境嵌入

如果Dashboard部署在服务器上（如 http://your-server.com:8501）：

```html
<iframe 
    src="http://your-server.com:8501?embed=true" 
    width="100%" 
    height="800px"
    frameborder="0"
    style="border: 1px solid #ddd; border-radius: 8px;">
</iframe>
```

### 方式4: 使用Streamlit Cloud

如果部署到Streamlit Cloud：

```html
<iframe 
    src="https://your-app.streamlit.app?embed=true" 
    width="100%" 
    height="800px"
    frameborder="0">
</iframe>
```

---

## 🔧 **Streamlit配置优化**

### 1. 隐藏Streamlit默认UI元素

创建 `.streamlit/config.toml`：

```toml
[client]
showErrorDetails = false
toolbarMode = "minimal"

[server]
headless = true
enableCORS = true
enableXsrfProtection = false

[browser]
gatherUsageStats = false

[theme]
primaryColor = "#667eea"
backgroundColor = "#FFFFFF"
secondaryBackgroundColor = "#F0F2F6"
textColor = "#262730"
font = "sans serif"
```

### 2. 修改Dashboard代码支持嵌入

在 `streamlit_app/aps_dashboard.py` 中添加：

```python
# 检测是否在iframe中
import streamlit as st

# 隐藏Streamlit默认元素
hide_streamlit_style = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stDeployButton {display:none;}
    </style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)
```

---

## 📱 **响应式设计**

### 自适应不同屏幕尺寸

```html
<style>
    .dashboard-responsive {
        width: 100%;
        height: 600px;
        border: none;
        border-radius: 8px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    
    @media (min-width: 768px) {
        .dashboard-responsive {
            height: 800px;
        }
    }
    
    @media (min-width: 1200px) {
        .dashboard-responsive {
            height: 1000px;
        }
    }
</style>

<iframe 
    class="dashboard-responsive"
    src="http://localhost:8501?embed=true">
</iframe>
```

---

## 🔐 **安全配置**

### 1. 启用HTTPS（生产环境必需）

```bash
# 使用nginx反向代理
server {
    listen 443 ssl;
    server_name your-domain.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://localhost:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 2. 添加访问控制

```html
<!-- 只允许特定域名嵌入 -->
<meta http-equiv="Content-Security-Policy" 
      content="frame-ancestors 'self' https://your-company.com;">
```

---

## 🎨 **自定义样式**

### 带品牌的嵌入页面

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>SAP生产预测 - 公司名称</title>
    <style>
        body {
            margin: 0;
            font-family: Arial, sans-serif;
            background: #f0f2f5;
        }
        
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px 30px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        
        .logo {
            font-size: 24px;
            font-weight: bold;
        }
        
        .stats {
            display: flex;
            gap: 20px;
            font-size: 14px;
        }
        
        .stat-item {
            text-align: center;
        }
        
        .stat-value {
            font-size: 20px;
            font-weight: bold;
        }
        
        .dashboard-frame {
            width: 100%;
            height: calc(100vh - 80px);
            border: none;
        }
    </style>
</head>
<body>
    <div class="header">
        <div class="logo">🏭 公司名称 - 生产预测系统</div>
        <div class="stats">
            <div class="stat-item">
                <div class="stat-value">84.8%</div>
                <div>准确率</div>
            </div>
            <div class="stat-item">
                <div class="stat-value">83.8%</div>
                <div>召回率</div>
            </div>
            <div class="stat-item">
                <div class="stat-value">0.902</div>
                <div>ROC AUC</div>
            </div>
        </div>
    </div>
    
    <iframe 
        class="dashboard-frame"
        src="http://localhost:8501?embed=true">
    </iframe>
</body>
</html>
```

---

## 🔗 **URL参数**

### Streamlit支持的URL参数

```
http://localhost:8501?embed=true              # 嵌入模式
http://localhost:8501?embed=true&theme=light  # 指定主题
http://localhost:8501?embed_options=show_toolbar,show_padding  # 显示工具栏
```

---

## 📦 **完整集成示例**

### React集成

```jsx
import React from 'react';

function SAPDashboard() {
  return (
    <div style={{ width: '100%', height: '100vh' }}>
      <iframe
        src="http://localhost:8501?embed=true"
        style={{
          width: '100%',
          height: '100%',
          border: 'none',
          borderRadius: '8px'
        }}
        title="SAP Production Delay Predictor"
        allow="clipboard-write"
      />
    </div>
  );
}

export default SAPDashboard;
```

### Vue.js集成

```vue
<template>
  <div class="dashboard-container">
    <iframe
      :src="dashboardUrl"
      class="dashboard-iframe"
      title="SAP Production Dashboard"
      frameborder="0"
      allowfullscreen
    />
  </div>
</template>

<script>
export default {
  name: 'SAPDashboard',
  data() {
    return {
      dashboardUrl: 'http://localhost:8501?embed=true'
    }
  }
}
</script>

<style scoped>
.dashboard-container {
  width: 100%;
  height: 100vh;
}

.dashboard-iframe {
  width: 100%;
  height: 100%;
  border: none;
}
</style>
```

### Angular集成

```typescript
// dashboard.component.ts
import { Component } from '@angular/core';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';

@Component({
  selector: 'app-dashboard',
  template: `
    <div class="dashboard-wrapper">
      <iframe 
        [src]="dashboardUrl" 
        class="dashboard-frame"
        frameborder="0">
      </iframe>
    </div>
  `,
  styles: [`
    .dashboard-wrapper {
      width: 100%;
      height: 100vh;
    }
    .dashboard-frame {
      width: 100%;
      height: 100%;
      border: none;
    }
  `]
})
export class DashboardComponent {
  dashboardUrl: SafeResourceUrl;

  constructor(private sanitizer: DomSanitizer) {
    this.dashboardUrl = this.sanitizer.bypassSecurityTrustResourceUrl(
      'http://localhost:8501?embed=true'
    );
  }
}
```

---

## 🚀 **部署到生产环境**

### 步骤1: 配置Streamlit服务器

修改 `.streamlit/config.toml`：

```toml
[server]
port = 8501
address = "0.0.0.0"
headless = true
enableCORS = true
enableXsrfProtection = false

[browser]
serverAddress = "your-domain.com"
serverPort = 8501
```

### 步骤2: 使用Nginx反向代理

```nginx
server {
    listen 80;
    server_name dashboard.your-company.com;
    
    # 重定向到HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name dashboard.your-company.com;
    
    ssl_certificate /etc/ssl/certs/your-cert.pem;
    ssl_certificate_key /etc/ssl/private/your-key.pem;
    
    location / {
        proxy_pass http://localhost:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket支持
        proxy_read_timeout 86400;
    }
}
```

### 步骤3: iframe嵌入代码（生产环境）

```html
<iframe 
    src="https://dashboard.your-company.com?embed=true" 
    width="100%" 
    height="800px"
    frameborder="0"
    style="border: 1px solid #ddd; border-radius: 8px;">
</iframe>
```

---

## 🎯 **高级功能**

### 1. 带参数的iframe（预选页面）

```html
<!-- 直接打开模型性能页面 -->
<iframe src="http://localhost:8501?embed=true&page=model_performance"></iframe>

<!-- 直接打开预测页面 -->
<iframe src="http://localhost:8501?embed=true&page=prediction"></iframe>
```

### 2. 动态切换Dashboard

```html
<script>
function switchDashboard(page) {
    const iframe = document.getElementById('dashboard-iframe');
    iframe.src = `http://localhost:8501?embed=true&page=${page}`;
}
</script>

<button onclick="switchDashboard('overview')">总览</button>
<button onclick="switchDashboard('model_performance')">模型性能</button>
<button onclick="switchDashboard('prediction')">延迟预测</button>
```

### 3. 全屏模式

```html
<button onclick="toggleFullscreen()">全屏</button>

<script>
function toggleFullscreen() {
    const iframe = document.getElementById('dashboard-iframe');
    if (iframe.requestFullscreen) {
        iframe.requestFullscreen();
    } else if (iframe.webkitRequestFullscreen) {
        iframe.webkitRequestFullscreen();
    }
}
</script>
```

---

## 📱 **移动端优化**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>SAP Dashboard - Mobile</title>
    <style>
        body {
            margin: 0;
            padding: 0;
            overflow: hidden;
        }
        
        .mobile-header {
            background: #667eea;
            color: white;
            padding: 10px;
            text-align: center;
            font-size: 16px;
            font-weight: bold;
        }
        
        #dashboard-iframe {
            width: 100%;
            height: calc(100vh - 50px);
            border: none;
        }
    </style>
</head>
<body>
    <div class="mobile-header">📊 SAP生产预测</div>
    <iframe 
        id="dashboard-iframe"
        src="http://localhost:8501?embed=true">
    </iframe>
</body>
</html>
```

---

## ⚙️ **配置选项**

### iframe属性说明

| 属性 | 说明 | 推荐值 |
|------|------|--------|
| `src` | Dashboard URL | `http://localhost:8501?embed=true` |
| `width` | 宽度 | `100%` |
| `height` | 高度 | `800px` 或 `100vh` |
| `frameborder` | 边框 | `0` |
| `allow` | 权限 | `clipboard-write` |
| `sandbox` | 安全限制 | 不建议使用（会限制功能） |

### URL参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `embed=true` | 嵌入模式 | `?embed=true` |
| `theme` | 主题 | `?theme=light` |
| `page` | 默认页面 | `?page=overview` |

---

## 🐛 **常见问题**

### Q1: iframe显示空白
**原因**: CORS跨域限制  
**解决**: 
```toml
# .streamlit/config.toml
[server]
enableCORS = true
enableXsrfProtection = false
```

### Q2: iframe无法交互
**原因**: 缺少权限  
**解决**: 添加 `allow="clipboard-write"` 属性

### Q3: 移动端显示异常
**原因**: 视口设置  
**解决**: 添加 viewport meta标签
```html
<meta name="viewport" content="width=device-width, initial-scale=1.0">
```

### Q4: 无法隐藏Streamlit菜单
**原因**: 跨域限制  
**解决**: 在Dashboard代码中添加CSS（见上方配置）

---

## 📊 **性能优化**

### 1. 预加载

```html
<link rel="preconnect" href="http://localhost:8501">
<link rel="dns-prefetch" href="http://localhost:8501">
```

### 2. 懒加载

```html
<iframe 
    src="about:blank" 
    data-src="http://localhost:8501?embed=true"
    loading="lazy"
    onload="this.src = this.dataset.src">
</iframe>
```

### 3. 缓存控制

```html
<iframe src="http://localhost:8501?embed=true&cache_bust=20260104"></iframe>
```

---

## 🎯 **推荐方案**

### 内网使用（推荐）

```html
<iframe 
    src="http://your-internal-server:8501?embed=true" 
    width="100%" 
    height="900px"
    frameborder="0"
    allow="clipboard-write"
    style="border: 1px solid #e0e0e0; border-radius: 8px;">
</iframe>
```

### 外网使用（需要HTTPS）

```html
<iframe 
    src="https://dashboard.your-company.com?embed=true" 
    width="100%" 
    height="900px"
    frameborder="0"
    allow="clipboard-write"
    style="border: 1px solid #e0e0e0; border-radius: 8px;">
</iframe>
```

---

## 📝 **完整HTML示例文件**

已创建示例文件：`examples/iframe_embed.html`

直接打开即可使用！

---

需要我创建具体的HTML示例文件吗？或者帮你集成到特定的Web框架中？
