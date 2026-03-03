# 沙特回国航班监控 (Saudi-to-China Flight Monitor)

实时监控从沙特阿拉伯（利雅得、吉达、达曼）飞往中国的所有航班状态。

## 功能

- **实时航班状态** — 通过 FlightRadar24 监控航班运营/取消/延误状态
- **历史追踪** — 记录冲突开始以来（2月28日）每日航班状态变化
- **多路线监控** — 直飞 + 经伊斯坦布尔/曼谷/新加坡/吉隆坡/德里等中转
- **空域状态** — 显示区域空域开放/关闭/受限情况
- **WhatsApp 通知** — 航班状态变化时实时推送 WhatsApp 消息
- **价格追踪** — 经济舱/商务舱价格监控
- **按机场分组** — 利雅得 RUH / 吉达 JED / 达曼 DMM 三大出发机场

## 快速开始

```bash
pip install -r requirements.txt

# 启动 Web 服务
evac serve

# 或直接使用 uvicorn
uvicorn emergency_flights.web:app --host 0.0.0.0 --port 8000
```

打开浏览器访问 `http://localhost:8000`

## 命令行

```bash
# 查看航班状态
evac find -s saudi_to_china

# 监控模式（自动刷新）
evac find -s saudi_to_china --watch

# 查看单个航班状态
evac status CZ5008
```

## WhatsApp 通知

WhatsApp 订阅入口默认隐藏，需在 Twilio 提交并获批 Content API 模板后再启用。

**启用步骤：**
1. 在 Twilio Console → Messaging → Content Templates 创建模板，3 个变量：`{{1}}` 时间戳，`{{2}}` 数量，`{{3}}` 正文
2. 提交 Meta 审批，获批后设置环境变量：
   ```
   TWILIO_ACCOUNT_SID=your_sid
   TWILIO_AUTH_TOKEN=your_token
   TWILIO_WHATSAPP_FROM=whatsapp:+15558376873
   WHATSAPP_CONTENT_SID=HXxxx  # 获批的模板 SID
   WHATSAPP_ALERTS_ENABLED=true
   ```
3. 网页将显示订阅入口，用户输入手机号即可订阅

## 部署

支持 Vercel、Render、Docker 部署，配置文件已包含。

## V1

原始版本（巴林撤离工具）保存在 `v1/` 目录中。
