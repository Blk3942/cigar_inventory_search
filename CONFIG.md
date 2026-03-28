# 配置文件使用说明

本文说明如何根据 [`config.example.json`](config.example.json) 编写自己的 `config.json`，并配合 `run_inventory.py` 导出多站点雪茄目录（含人民币与税后估算）。

## 快速开始

1. 复制示例为正式配置（文件名必须是 `config.json` 若使用默认命令）：

   ```powershell
   copy config.example.json config.json
   ```

2. 编辑 `config.json`：至少确认 `sites` 里各站点的 `base_url`、`currency` 正确。

3. 运行导出：

   ```powershell
   python run_inventory.py -o inventory_report.csv
   ```

   指定配置文件路径：

   ```powershell
   python run_inventory.py -c my-config.json -o report.csv
   ```

   输出 JSON：

   ```powershell
   python run_inventory.py --format json -o report.json
   ```

---

## 导出表列（当前）

| 列名 | 说明 |
|------|------|
| 网站 | 配置中的 `display_name` |
| 品牌 | 推断的品牌名 |
| 产品名称 | 商品标题 |
| 规格 | 变体规格文案 |
| 原价货币 / 原价金额 | 站点标价 |
| 人民币税前 | 按运行当次汇率折算 |
| 人民币税后 | 税前 × (1 + `tariff_rate`) |
| 解析雪茄支数 | 能从规格等解析出支数时填写，否则为空 |
| 单支人民币税后 | 税后总价 ÷ 解析支数；无支数时为空 |
| 链接 | 商品页 URL |

为便于阅读，**不导出**：汇率明细文案、关税比例、单支税前价、店铺库存数量（抓取时仍会按 `include_unavailable` 过滤无货，只是表中不再显示库存列）。

---

## 顶层字段一览

| 字段 | 类型 | 说明 |
|------|------|------|
| `sites` | 数组 | 要抓取的网站列表，见下文。 |
| `filters` | 对象 | 品牌、产品、价格筛选，见下文。 |
| `brand_hints` | 字符串数组 | 用于**推断导出表中的「品牌」列**（与 `filters.brands` 配合），见下文。 |
| `tariff_rate` | 数字 | 关税/税费比例，**小数形式**。`0.5` 表示在**人民币税前价**基础上再加 50%，即税后 = 税前 × (1 + 0.5)。 |
| `include_unavailable` | 布尔 | `false`（默认）只导出当前可下单的变体；`true` 时包含无货变体。 |

---

## `sites`：多网站配置

每个元素描述一个店铺。`adapter` 决定抓取方式；见下文 **已实现的 adapter**。

| 字段 | 必填 | 说明 |
|------|------|------|
| `id` | 建议填 | 站点内部标识，便于区分日志或以后扩展。未填时会用 `base_url` 等兜底。 |
| `display_name` | 建议填 | 导出表 **「网站」** 列显示的名称。也可用 `name`，二者等价（优先 `display_name`）。 |
| `base_url` | **必填** | 店铺根地址，**不要**末尾斜杠，例如 `https://cigarviu.com`。 |
| `adapter` | 可选 | 默认 `"shopify"`。 |
| `currency` | **必填** | 与店铺标价一致的 **ISO 货币代码**（如 `CHF`、`EUR`、`USD`），用于换汇。 |
| `only_cigar_related` | 可选 | 默认 `true`：只保留 `product_type` / `tags` 与 cigar 相关的商品。 |
| `enabled` | 可选 | 默认 `true`。设为 **`false`** 时**整站不会参与抓取**（结果里不会出现该站）。 |
| `max_pages` | 可选 | **Shopify / WooCommerce / Magento**：API 分页页数上限；**HTML 类适配器**：列表翻页次数上限。`null` 时各适配器自有默认。 |
| `adapter_options` | 可选 | 传给具体适配器的参数（字典），见下表。 |

### 已实现的 `adapter` 取值

| adapter | 说明 |
|---------|------|
| `shopify` | 公开 `/products.json` 分页。 |
| `woocommerce` | WordPress **WooCommerce Store API**：`/wp-json/wc/store/v1/products`（可在 `adapter_options.wc_store_namespace` 覆盖命名空间）。价格按接口的 `currency_minor_unit` 换算。 |
| `magento2` | **GraphQL** `POST {base}/graphql`。默认使用 `filter: { price: { from: "0", to: "99999999" } }` 分页（部分德区店要求必须带 search/filter）。可在 `adapter_options.magento_graphql_search` 指定搜索词改为 `search:` 查询；`page_size`、`graphql_path` 可配。 |
| `prestashop` | 读 `sitemap.xml`（及常见 `sitemap` 子索引）中的商品 URL，再抓页面 **JSON-LD / meta** 取价。`adapter_options.max_scrape_products` 限制条数。 |
| `oscommerce` | 针对 **Tecon** 类 osCommerce：默认从雪茄分类 `cPath` 列表页解析 `product_info.php?products_id=`，再逐页抓详情。`adapter_options.seed_urls` 可覆盖种子列表。 |
| `xtcommerce` | 针对 **Tabak Träber** 类 xt:Commerce SEO 链接：从 `Zigarren:::…` 列表解析商品 `.html` 链接再抓详情。`adapter_options.seed_urls` 可覆盖。 |
| `custom` | **The Cigar Smoker** 类：从首页提取 `/shop/…-p数字` 链接并抓详情价（JSON-LD / meta / € 正则）。 |

**注意：**

- HTML 抓取受页面改版影响大，且已做条数/翻页上限，**价格与库存仅供对照**，不保证与结账页一致。  
- **Magento 全店**商品含烟斗、配件等，示例配置里 **Falkum / Selected Cigars** 使用 **`only_cigar_related`: `false`**，请主要靠 **`filters.brands`** 等缩小范围。  
- `currency` 必须与站点标价货币一致（用于 Frankfurter 换汇）。  
- 个别站（如 Cloudflare 保护的 Shopify）仍可能 403，该站会跳过并打印原因。

[`config.example.json`](config.example.json) 中示例站点的 `adapter` / `currency` 依据官网标价与常见建站方式填写，摘要如下：

| 站点 | adapter | currency | 说明（网页侧） |
|------|---------|----------|----------------|
| Cigar VIU | shopify | CHF | 瑞士，Shopify（示例中 `enabled: true`） |
| LCDH Bonn | woocommerce | EUR | 德国，标价 € |
| Tecon GmbH | oscommerce | EUR | 德国，标价 €（类 osCommerce / Zen 架构） |
| Tabak Träber | xtcommerce | EUR | 德国，xt:Commerce 风格 |
| Falkum | magento2 | EUR | 德国，Magento |
| Selected Cigars | magento2 | EUR | 德国，标价 € |
| The Cigar Smoker | custom | EUR | LCDH Hamburg，标价 € |
| Cigar Must | prestashop | CHF | 瑞士，PrestaShop，标价 CHF |
| La Casa del Habano Nyon | shopify | CHF | 瑞士；常见 **Cloudflare 403**，脚本可能无法拉取（示例中 `enabled: false`） |
| Siglo Mundo | shopify | CHF | 瑞士，Shopify 公开 JSON 可访问（示例中 `enabled: true`，与 Cigar VIU 一并导出） |

---

## `filters`：筛选条件

所有列表类字段：**空数组 `[]` 表示不启用该项筛选**（全部放行，仍受站点 `only_cigar_related` 等约束）。

| 字段 | 类型 | 说明 |
|------|------|------|
| `brands` | 字符串数组 | 非空时：商品在 **标题、标签、厂商、handle** 组成的文本中，须 **包含** 其中任一品牌（子串匹配，不区分大小写）。 |
| `product_keywords` | 字符串数组 | 非空时：**标题** 须包含其中 **任意** 一个关键词（子串，不区分大小写）。 |
| `product_handles` | 字符串数组 | 非空时：商品的 **handle**（URL 中 `/products/` 后一段）须在该列表中（不区分大小写）。 |
| `price_cny_pre_tax_min` | 数字或 `null` | 按 **折算后的人民币税前价** 设下限；`null` 表示不限制。 |
| `price_cny_pre_tax_max` | 数字或 `null` | 按 **折算后的人民币税前价** 设上限；`null` 表示不限制。 |

**筛选逻辑简述：**

- 各条件为 **AND** 关系（例如既满足品牌，又满足关键词，又在价格区间内）。
- 价格在 **换汇之后** 再比较；汇率每次运行会实时请求（见下文「汇率说明」）。

### 配置示例片段

只关心 **Cohiba** 与 **Montecristo**，且标题里出现 **Siglo**：

```json
"filters": {
  "brands": ["Cohiba", "Montecristo"],
  "product_keywords": ["Siglo"],
  "product_handles": [],
  "price_cny_pre_tax_min": 500,
  "price_cny_pre_tax_max": 8000
}
```

只锁定 **指定商品页**（handle 在 Shopify 后台或商品 URL 中可查）：

```json
"filters": {
  "brands": [],
  "product_keywords": [],
  "product_handles": ["cohiba-siglo-2-slb-25"],
  "price_cny_pre_tax_min": null,
  "price_cny_pre_tax_max": null
}
```

---

## `brand_hints`：品牌列如何显示

导出表中的 **「品牌」** 列按以下顺序推断：

1. 在 **标题 + 标签** 文本中，查找是否在子串意义上命中 **`filters.brands` 与 `brand_hints` 合并后的名称**（**长名称优先**，避免短词抢匹配）。
2. 若未命中，则用 **第一个标签**，再没有则用 **厂商（vendor）**，否则为 `—`。

因此：

- 当 **`filters.brands` 非空** 时，列表里的名字既用于 **过滤**，也参与 **品牌列** 的匹配。
- 当 **`filters.brands` 为空** 时，仍可通过 **`brand_hints`** 提供常见牌号，让「品牌」列更可读（否则可能只剩厂商名或标签）。

可按需增删 `brand_hints` 中的字符串，无需改代码。

---

## `tariff_rate` 与税后人民币

- **人民币税前**：站点原价 × 运行当次汇率（折算为 CNY）。
- **人民币税后**：税前 × (1 + `tariff_rate`)。
- 默认 `tariff_rate` 为 `0.5`，即税后 = 税前 × 1.5。

这仅为配置驱动的 **估算模型**，不代表实际海关或税务规定。若要改为例如 30%，可设 `"tariff_rate": 0.3`。

---

## 汇率说明

程序使用 [Frankfurter](https://www.frankfurter.app/) 公开接口在 **每次运行** 时拉取最新参考汇率（各站点货币 → CNY），用于计算「人民币税前 / 税后」。导出表中**不再单独列出**汇率原文，避免表格过宽。

该汇率与银行挂牌价或海关计税所用汇率可能不同，**仅作参考**。

---

## 「解析雪茄支数」与单支税后价

当 **规格**（或「默认」规格下的 **标题 / handle**）中能识别出整盒、整包支数时，导出表会填写 **解析雪茄支数**，并计算 **单支人民币税后**（`人民币税后 ÷ 支数`）。**单支税前**不再导出。

常见可识别写法包括（不区分大小写）：`Box of 25`、`Jar of 20`、`Pack of 10`、`Single piece`、`[6]`、`SLB 25` / `BN-25`（多在 handle 或标题中）、`10 支` 等。

**注意：**

- 规格为 **Silver / Gold** 等无支数信息时，不会用标题「猜」支数，避免颜色规格串行。
- 迷你茄、拼盘、混装等若文案格式特殊，可能 **解析失败**，支数与单支税后为空。
- 单支价 **隐含假设**：标价对应一整盒/一整包且支数解析正确；礼盒、套装若实为多品类组合，单支价仅作参考。

实现见 `cigar_inventory/stick_count.py`。

---

## 关于库存「数量」

Shopify 公开接口通常**无法**给出可靠库存支数。脚本仍按 `include_unavailable` 决定是否包含无货变体，但**导出表中已省略库存数量列**。

---

## 与单站脚本的关系

仅抓取 **Cigar VIU**、且不需要多站/汇率/关税列时，仍可使用：

```powershell
python cigarviu_inventory.py fetch -o inventory.csv
```

多站、筛选、人民币与税后可估列请统一使用 **`run_inventory.py` + `config.json`**。

---

## 文件对照

| 文件 | 用途 |
|------|------|
| `config.example.json` | 示例模板，可复制后修改。 |
| `config.json` | 本地实际使用配置（建议勿提交含隐私的定制内容；仓库中可用 `.gitignore` 忽略）。 |

如有字段与代码不一致，以 `cigar_inventory/config_loader.py` 中的解析逻辑为准。
