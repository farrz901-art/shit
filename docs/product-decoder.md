# 产品订货号解析服务

## 添加新系列

1. 在 `configs/product_decoders/<category>/<vendor>/` 下新建 YAML
2. 复制 `configs/product_decoders/motor/siemens/1le0_low_voltage.yaml` 的结构，按实际编码规则修改
3. 填好 `router.prefix` 和 `router.pattern`
4. 重启服务即可

**零代码改动**。模型前缀路由 (`ProductDecoder.route()`) 自动选配置。

## 配置目录

`configs/product_decoders/` 是默认的产品配置目录，**部署数据**而非代码：

- 加新厂商/新系列：直接在此目录下加 YAML
- 多环境覆盖：用环境变量 `PRODUCT_DECODERS_CONFIGS=/path/to/other/configs` 启动服务即可
- 默认路径用 `Path(__file__).resolve()` 推导，**不依赖 CWD**

## 统一输出 Schema

```json
{
  "series": "siemens_1le0_low_voltage",
  "manufacturer": "Siemens",
  "raw_input": "1LE0001-1AA42-1AA4",
  "normalized": "1LE00011AA421AA4",
  "display": "1LE0001-1AA42-1AA4",
  "prefix": "1LE000",
  "efficiency_grade": "EFF3",
  "efficiency_grade_zh": "高效电动机，中国能效等级 3 级",
  "efficiency_grade_en": "High Efficiency, China Energy Efficiency Grade 3",
  "frame_size": 100,
  "frame_size_zh": "100mm 机座",
  "frame_size_en": "100mm frame",
  "frame_size_raw": "1A",
  "poles": 2,
  "poles_zh": "2 极",
  "poles_en": "2 poles",
  "poles_raw": "A",
  "frame_length": "L",
  "frame_length_zh": "长机座",
  "frame_length_en": "long",
  "frame_length_raw": "4",
  "voltage": "220VD/380VY/50",
  "voltage_zh": "220VD/380VY 50Hz",
  "voltage_en": "220VD/380VY 50Hz",
  "voltage_raw": "21",
  "mounting": "IM B3",
  "mounting_zh": "IM B3 卧式底脚安装",
  "mounting_en": "IM B3",
  "mounting_raw": "A",
  "winding_protection": "NONE",
  "winding_protection_zh": "无绕组保护 / without winding protection",
  "winding_protection_en": "without winding protection",
  "winding_protection_raw": "A",
  "box_location": "TOP",
  "box_location_zh": "置顶 / on top",
  "box_location_en": "on top",
  "box_location_raw": "4"
}
```

**设计要点**：
- 主值用 `code` 或简短中文（如 `"L"`、`"IM B3"`），方便程序处理
- `_zh` / `_en` 后缀字段提供完整中文/英文说明
- `_raw` 后缀字段保留原始编码，方便追溯
- `display` 字段是按 YAML `position.group` 视觉分组还原的展示形式

## API 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/decode` | 解码一个型号，body: `{"model": "..."}` |
| `GET`  | `/series` | 列出所有支持系列 |
| `GET`  | `/health` | 健康检查，返回 `series_count` |

## Dify 工作流接入

```
[开始] 用户输入: "1LE0001-1AA42-1AA4"
   ↓
[HTTP 请求节点]
   POST http://localhost:8000/decode
   Body: {"model": "{{sys.query}}"}
   ↓
[LLM 节点] 格式化输出
   Prompt: "你是产品选型助手，根据解码结果用中文分点解释。
            {{#http_response.body#}}"
   ↓
[直接回复]
```

## 解码示例

输入：`1LE0001-1AA42-1AA4`（16 字符，标准化后 `1LE00011AA421AA4`，4 段 display）

| 位置 | 编码 | group | 含义 |
|---|---|---|---|
| 1-6 | `1LE000` | 1 | 型号前缀（低压系列） |
| 7 | `1` | 1 | 能效等级 3 级 |
| 8-9 | `1A` | 2 | 机座号 100 |
| 10 | `A` | 2 | 2 极 |
| 11 | `4` | 2 | 长机座 L |
| 12-13 | `21` | 3 | 220VD/380VY 50Hz |
| 14 | `A` | 4 | IM B3 安装 |
| 15 | `A` | 4 | 无绕组保护 |
| 16 | `4` | 4 | 接线盒置顶 |
