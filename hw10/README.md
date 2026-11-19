# Nand2Tetris VM（第 7、8 章）

Python 實作的堆疊虛擬機，包含兩個互補的部分：

| 模組 | 功能 |
|------|------|
| `VMTranslator.py` | **VM 翻譯器**：把 `.vm` 展開成 Hack 組合語言 `.asm`（第 7、8 章的標準成果） |
| `VMEmulator.py` | **VM 直譯器**：直接執行 `.vm`，模擬 SP / LCL / ARG / THIS / THAT 與呼叫框架 |
| `HackCPU.py` | 小型 Hack CPU，用來把翻譯後的 `.hack` 真正跑起來、與直譯器交叉驗證 |

支援完整指令集：

- 算術邏輯：`add sub neg eq gt lt and or not`
- 記憶體存取：`push/pop constant local argument this that temp pointer static`
- 流程控制：`label goto if-goto`
- 函式：`function call return`
- 多檔案 bootstrap：`SP = 256` 後 `call Sys.init 0`

## 快速開始

直接雙擊：

- `demo.bat`：翻譯 `examples/SimpleAdd.vm` → 用 `../hw9/Assembler.py` 組譯 → 同時用 VM 直譯器與 Hack CPU 執行，比對結果
- `run_tests.bat`：執行全部 38 個測試
- `translate.bat`：把任何 `.vm` 檔或資料夾拖曳上去即可翻譯
- `emulate.bat`：把 `.vm` 檔或資料夾拖曳上去即可執行（最多 5000 步）

## 命令列

### 翻譯器

```sh
# 單一檔案：不產生 bootstrap
python VMTranslator.py examples/SimpleAdd.vm examples/SimpleAdd.asm

# 資料夾：所有 .vm 一起翻譯，自動加 bootstrap
python VMTranslator.py examples/Project examples/Project.asm
```

若省略輸出檔名，預設為同名 `.asm`（資料夾則是 `資料夾名.asm`）。

### VM 直譯器

```sh
python VMEmulator.py examples/SimpleAdd.vm
python VMEmulator.py examples/Project          # 資料夾 → 自動 bootstrap
python VMEmulator.py A.vm B.vm Sys.vm --steps 5000
```

輸出暫存器、堆疊與 static 變數。程式若不停（例如 OS 主迴圈），用 `--steps` 限制步數。

### Hack CPU

```sh
python HackCPU.py examples/SimpleAdd.hack --steps 100000
```

CLI 預設會把 `SP` 設成 256（單檔翻譯沒有 bootstrap，但 VM 模擬器會這樣做）。

## Python API

```python
from VMTranslator import translate, translate_file
from VMEmulator import VMEmulator
from HackCPU import HackCPU

asm = translate([("Foo.vm", "push constant 7\npush constant 8\nadd\n")])
output_path, count = translate_file("Foo.vm")          # Foo.asm

vm = VMEmulator()
vm.load([("Foo.vm", "push constant 7\npush constant 8\nadd\n")])
vm.run()
print(vm.stack())       # [15]
print(vm.registers)     # {'SP': 257, 'LCL': 0, 'ARG': 0, ...}
```

端到端串接（需 `hw9/Assembler.py`）：

```python
from Assembler import Assembler
from VMTranslator import translate
from VMEmulator import VMEmulator
from HackCPU import HackCPU

files = [("SimpleAdd.vm", "push constant 7\npush constant 8\nadd\n")]
cpu = HackCPU().load(Assembler().assemble(translate(files)))
cpu.memory[0] = 256                 # 單檔翻譯沒有 bootstrap，手設 SP
cpu.run()

vm = VMEmulator(); vm.load(files); vm.run()
assert cpu.memory[256] == vm.memory[256] == 15
```

## 記憶體段對照

| VM 段 | Hack 實作 |
|-------|-----------|
| `constant i` | 立即值 `D=A`，不佔 RAM |
| `local i` | `RAM[LCL + i]` |
| `argument i` | `RAM[ARG + i]` |
| `this i` / `that i` | `RAM[THIS + i]` / `RAM[THAT + i]` |
| `temp i` | `RAM[5 + i]`（i = 0..7） |
| `pointer 0/1` | `THIS` / `THAT`（RAM[3] / RAM[4]） |
| `static i` | 符號 `檔名.i`，由組譯器從 RAM[16] 開始配置 |

`eq / gt / lt` 以 `TRUE_n` / `END_n` 標記展開，結果固定是 `-1`（true）或 `0`（false）。

## 呼叫框架（第 8 章）

`call f nArgs`：

1. push 返回位址 `f$ret.k`
2. push LCL、ARG、THIS、THAT
3. `ARG = SP - 5 - nArgs`
4. `LCL = SP`
5. `goto f`，並定義 `(f$ret.k)`

`return`：

1. `frame = LCL`（存 R13），`retAddr = *(frame-5)`（存 R14）
2. `*ARG = pop()`，`SP = ARG + 1`
3. 由 `frame-1 .. frame-4` 依序還原 THAT、THIS、ARG、LCL
4. `goto retAddr`

多檔案翻譯時，`label/goto/if-goto` 的標記會加上 `函式名$` 前綴，避免不同類別的 `LOOP` 相撞；`static` 則用 `檔名.i` 區隔。

## 測試

```sh
python -m unittest discover -s tests -v
```

- `test_translator.py`：每條 VM 指令的精確 Hack 展開、錯誤處理、bootstrap、static、label scope
- `test_emulator.py`：算術、記憶體段、迴圈、遞迴、多檔案函式與 static
- `test_integration.py`：`.vm → .asm → .hack → Hack CPU` 與直譯器的 RAM 狀態比對。直譯器會寫入 R13/R14，並推入與翻譯碼相同的 ROM 返回位址，因此是**完整逐字比對全部 RAM**，沒有任何例外或啟發式跳過。

## 參考資料

- Nand2Tetris 第 7、8 章投影片（Stack Arithmetic / Program Control）
- <https://github.com/ccc115a/co/tree/main/nand2tetris/08>（`vm2asm.c`：VM → Hack 翻譯器）
- <https://github.com/ccc-js/hack-computer/tree/main/lib/vm>（`hackemu.js`、`vmparse.js`）
- <https://github.com/951220lynnjmes-jpg/_co/tree/main/06>（第 6 章 `.asm` 範例）
- 同一專案的 `../hw9/Assembler.py`（Hack 組譯器）
