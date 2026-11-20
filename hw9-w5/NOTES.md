# 第 10 週作業筆記：把套件發佈到公開套件庫

> 任務：寫一個套件並發佈到公開的套件庫（PyPI / npm / crates.io）。
> 可延伸：把上週的 Cloudflare app 部署或包成套件。

---

## 0. 任務拆解

- 選一個生態系，做出「可被別人安裝」的套件
- 套件要能被 `pip install` / `npm install` / `cargo install` 安裝
- 原始碼、README、LICENSE、版本號要齊全
- 發佈後在公開頁面看得到，且能實際安裝成功

| 路線 | 套件庫 | 適合的現有作品 | 安裝指令 |
| --- | --- | --- | --- |
| Python | PyPI | `hw9` Hack 組譯器、`539` 樂透分析 | `pip install <name>` |
| Node.js | npm | CLI 工具、前端工具、Cloudflare app 包裝 | `npm install -g <name>` |
| Rust | crates.io | `hw7` todo-app | `cargo install <name>` |
| Cloudflare | Pages（部署，非套件庫） | `water-reminder` | 開網址使用 |

建議：
- 想最快完成 → 用 `hw9/Assembler.py` 發上 PyPI（純標準庫、無依賴）
- 想挑戰 → 用 `hw7` 發上 crates.io
- 上週作品 → `water-reminder` 用 `wrangler` 部署到 Cloudflare Pages

---

## 1. 共通前置作業

- [ ] 註冊對應帳號（PyPI / npm / crates.io）
- [ ] 開啟兩步驟驗證（2FA），並建立 API Token
- [ ] 決定套件名稱（全球唯一，先到官網搜尋是否被用走）
- [ ] 版本號採 SemVer：`0.1.0`（首次發佈用 0.x）
- [ ] 補齊 `README.md`、`LICENSE`（例如 MIT）
- [ ] 憑證只放環境變數或登入檔，**不要 commit 進 git**
- [ ] 先打包 + 本機安裝測試，再上傳正式站

---

## 2. Python → PyPI（以 hw9 Assembler 為例）

### 2.1 專案結構（最小可發佈）

```
hw9/
├── pyproject.toml
├── README.md
├── LICENSE
├── Assembler.py          # 內含 def main(argv=None)
├── examples/
│   └── Add.asm
└── tests/
    └── test_assembler.py
```

### 2.2 `pyproject.toml` 範本

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "hack-assembler-lynn"
version = "0.1.0"
description = "Nand2Tetris Hack assembler (asm -> hack)"
readme = "README.md"
requires-python = ">=3.9"
license = { text = "MIT" }
authors = [{ name = "lynn" }]

[project.urls]
Homepage = "https://github.com/951220lynnjmes-jpg/t6g4"

[project.scripts]
hack-asm = "Assembler:main"

[tool.setuptools]
py-modules = ["Assembler"]
```

重點：
- `name` 必須全站唯一，可加前後綴避免撞名
- `[project.scripts]` 讓安裝後可直接執行 `hack-asm Add.asm`
- 若改用 `src/` 套件結構，把 `Assembler.py` 放進套件資料夾並改 `packages`

### 2.3 建置與本機測試

```sh
python -m venv .venv
.venv\Scripts\activate
pip install build
python -m build
dir dist
pip install dist\hack_assembler_lynn-0.1.0-py3-none-any.whl
hack-asm examples\Add.asm
```

### 2.4 上傳

```sh
pip install twine
twine check dist/*
twine upload dist/*          # 帳號用 __token__，密碼貼 PyPI API Token
```

建議先上 **TestPyPI** 練手：

```sh
twine upload --repository testpypi dist/*
pip install -i https://test.pypi.org/simple/ hack-assembler-lynn
```

### 2.5 驗證

- 到 `https://pypi.org/project/hack-assembler-lynn/` 看頁面
- 開新環境 `pip install hack-assembler-lynn` 再執行一次

---

## 3. Node.js → npm

### 3.1 `package.json` 重點欄位

```json
{
  "name": "water-reminder-cli",
  "version": "0.1.0",
  "description": "喝水提醒 CLI / PWA helper",
  "type": "module",
  "bin": { "water-reminder": "./bin/cli.js" },
  "files": ["bin", "public"],
  "license": "MIT",
  "repository": { "type": "git", "url": "https://github.com/951220lynnjmes-jpg/t6g4" }
}
```

- `private` 要移除或設為 `false`，否則不能發佈
- `files` 控制打包內容，避免把測試、node_modules 帶上去
- `bin` 提供 CLI 入口（檔案第一行加 `#!/usr/bin/env node`）
- scoped 名稱（`@user/pkg`）需加 `--access public`

### 3.2 打包與發佈

```sh
npm pack --dry-run        # 預覽會打包哪些檔案
npm login
npm publish               # scoped 套件：npm publish --access public
npm view water-reminder-cli
npx water-reminder-cli
```

---

## 4. Rust → crates.io（以 hw7 為例）

### 4.1 `Cargo.toml` 補 metadata

```toml
[package]
name = "todo-app-lynn"
version = "0.1.0"
edition = "2021"
description = "A small axum todo app"
license = "MIT"
repository = "https://github.com/951220lynnjmes-jpg/todo-app"
readme = "README.md"
keywords = ["todo", "axum"]
categories = ["web-programming"]
exclude = ["target/*", "test-results/*"]
```

- crates.io 名稱不可重複，`todo-app` 很可能已被使用，先查詢再加後綴
- 一定要有 `description` 與 `license`，否則 `cargo publish` 會擋
- 不要把 `target/`、測試產物打包進去

### 4.2 發佈流程

```sh
cargo login <CRATES_IO_TOKEN>
cargo package --list      # 預覽打包清單
cargo publish --dry-run
cargo publish
cargo install todo-app-lynn
```

### 4.3 驗證

- `https://crates.io/crates/todo-app-lynn`
- `https://docs.rs/todo-app-lynn` 會自動產生文件

---

## 5. 上週 Cloudflare app（water-reminder）

### 選項 A：直接部署（這是「上線」，不是套件庫）

```sh
npx wrangler pages deploy public --project-name water-reminder-tw
```

- `wrangler.jsonc` 已有 `pages_build_output_dir: ./public`
- 部署後會得到 `*.pages.dev` 公開網址

### 選項 B：包成 npm 套件（符合「公開套件庫」）

- 把 `public/` 靜態檔與 CLI 放進 `files`
- `bin` 指向啟動 script（例如用 `wrangler` 或本機靜態伺服器）
- `npm publish` 後即可 `npx` 執行

> 若老師的重點是「公開套件庫」，選項 B 才算套件；選項 A 屬部署。

---

## 6. 常見錯誤與排解

| 症狀 | 原因 | 解法 |
| --- | --- | --- |
| 名稱已被使用 | 名稱不唯一 | 加個人前綴或後綴 |
| 401 Unauthorized | Token 錯或過期 | 重新產生 API Token |
| `private: true` | npm 不允許發佈 | 移除 `private` |
| crates 缺 license/description | metadata 不全 | 補齊 `Cargo.toml` |
| 打包帶入多餘檔案 | 未設 `files` / `exclude` | 用 `npm pack --dry-run`、`cargo package --list` 檢查 |
| 安裝後找不到指令 | `bin` 或 `scripts` 沒設好 | 補 `[project.scripts]` / `package.json` 的 `bin` |
| 版本已存在 | 同版本不能重傳 | 升版本號（`0.1.1`） |

---

## 7. 驗收清單

- [ ] 公開頁面可開啟（PyPI / npm / crates.io）
- [ ] 全新環境可安裝成功
- [ ] 安裝後可實際執行功能（不是空殼）
- [ ] README 有安裝與使用範例
- [ ] 有 LICENSE
- [ ] 版本號與 git tag 對得上
- [ ] 未把 token / 密鑰寫進 repo

---

## 8. 建議時程

| 階段 | 內容 |
| --- | --- |
| 1 | 選路線、註冊帳號、開 2FA、申請 token |
| 2 | 整理專案結構、補 `pyproject.toml` / `package.json` / `Cargo.toml` |
| 3 | 本機 build + 安裝測試 |
| 4 | 上 TestPyPI 或 `--dry-run` 預演 |
| 5 | 正式發佈 + 驗證 + 寫筆記/截圖 |

---

## 9. 參考連結

- 範例：https://pypi.org/project/rstatistics/
- 範例：https://crates.io/crates/rucloud
- PyPI：https://pypi.org/
- TestPyPI：https://test.pypi.org/
- npm：https://www.npmjs.com/
- crates.io：https://crates.io/
- Cloudflare Pages：https://pages.cloudflare.com/
