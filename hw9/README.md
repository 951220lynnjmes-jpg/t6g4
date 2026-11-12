# Nand2Tetris Assembler (Hack)

這是 nand2tetris Project 6 的 Hack 組譯器，使用 Python 實作。

## 功能

- 將 `.asm` 檔組譯成 16 位元的 `.hack` 機器碼
- 支援註解、空行與多餘空白
- 支援標籤 `(LABEL)` 與變數自動配置（從 RAM[16] 開始）
- 內建符號：`SP`、`LCL`、`ARG`、`THIS`、`THAT`、`R0`～`R15`、`SCREEN`、`KBD`
- 支援完整 A-instruction 與 C-instruction（dest、comp、jump）

## 最簡單的測試方式

直接雙擊：

- `demo.bat`：組譯 `examples/Add.asm`，並顯示產生的機器碼
- `run_tests.bat`：執行全部單元測試
- `assemble.bat`：把任何 `.asm` 檔拖曳到這個檔案上即可組譯

## 命令列使用方式

```sh
python Assembler.py Add.asm
```

預設會在同一資料夾產生 `Add.hack`。也可以指定輸出檔名：

```sh
python Assembler.py Add.asm output.hack
```

## 執行測試

```sh
python -m unittest discover -s tests -v
```

## 檔案說明

- `Assembler.py`：組譯器主程式與命令列介面
- `tests/test_assembler.py`：單元測試
- `examples/Add.asm`：範例程式
- `demo.bat`、`run_tests.bat`、`assemble.bat`：Windows 快速操作腳本
