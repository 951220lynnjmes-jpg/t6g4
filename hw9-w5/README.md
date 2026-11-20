# hack-assembler-lynn

Nand2Tetris Project 6 的 Hack 組譯器，把 `.asm` 檔轉成 16 位元的 `.hack` 機器碼。

## 安裝

```sh
pip install hack-assembler-lynn
```

## 命令列用法

```sh
hack-asm Add.asm            # 產生 Add.hack
hack-asm Add.asm out.hack   # 指定輸出檔名
```

也可以直接跑模組：

```sh
python -m hack_assembler Add.asm
```

## Python API

```python
from hack_assembler import Assembler, assemble_file

binary = Assembler().assemble("@2\nD=A\n")
print("\n".join(binary))
# 0000000000000010
# 1110110000010000

output_path, count = assemble_file("Add.asm")
print(f"{output_path} ({count} instructions)")
```

## 功能

- 支援 A-instruction 與 C-instruction（dest / comp / jump）
- 支援註解、空行、多餘空白
- 支援標籤 `(LABEL)` 與變數，變數從 RAM[16] 開始配置
- 內建符號：`SP`、`LCL`、`ARG`、`THIS`、`THAT`、`R0`～`R15`、`SCREEN`、`KBD`
- 遇到非法語法會丟出 `AssemblyError`

## 開發

```sh
python -m venv .venv
.venv\Scripts\activate
pip install -e .
python -m unittest discover -s tests -v
```

建置與發佈：

```sh
pip install build twine
python -m build
twine check dist/*
twine upload dist/*
```

## License

MIT
