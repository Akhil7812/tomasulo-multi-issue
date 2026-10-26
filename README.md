# Multi-issue Tomasulo simulator (ROB + RAT + LSQ + 1-bit branch predictor)

Python 3 (no external packages).

## Run
```
cd code
python main.py ../tests/test1_loop.txt                  # width taken from the file ("Issue width = N", default 1)
python main.py ../tests/test1_loop.txt --issue-width 4  # override the width (1..4)
python main.py file.txt --issue-width 2 --cdb-width 1 --commit-width 1
cd ../tests && python run_tests.py                      # all tests, widths 1-4, checked against a reference interpreter + 400 random programs
```

## Input file (one text file)
```
# of rs   Cycles in EX  Cycles in Mem  # of FUs        <- hardware table (rows: Integer adder, FP adder,
Integer adder   2   1        1                            FP multiplier, Load/store unit); Mem column blank/'-'
FP adder        3   3        1                            for the ALUs
FP multiplier   2   20       1
Load/store unit 3   1   4    1
ROB entries = 128
Issue width = 2            (1..4, default 1)
CDB width = 2              (optional, default = issue width)
Commit width = 2           (optional, default = issue width)
R1=10, R2=20, F2=30.1      (registers not listed = 0)
Mem[4]=1, Mem[8]=2         (byte addresses, 256 B memory)
Add.d F1, F2, F3           (program; case-insensitive, commas optional)
Ld F4, 8(R1)
Bne R2, R3, -3             (offset in INSTRUCTIONS: target = pc+1+offset, i.e. PC+4+offset<<2)
```
## Output
Instruction status table (ISSUE / EX / MEM / WB / COMMIT cycles, committed instructions in commit order; a
loop appears once per dynamic iteration), register values, non-zero memory, and cycle/IPC/branch statistics.

## Files
| file | stage / role |
|---|---|
| `code/init.py` | data structures, input parser, `Machine` (all pipeline state) |
| `code/issue.py` | ISSUE: **multi-issue (1..4, in order)**, renaming, 1-bit predictor + 8-entry BTB |
| `code/exe.py` | EX: ALUs, address adder, branch resolution, **squash/recovery** |
| `code/mem.py` | MEM: load/store queue, disambiguation, store-to-load forwarding, single memory port |
| `code/wb.py` | WB: CDB broadcast (**several results per cycle**) |
| `code/commit.py` | COMMIT: **several in-order commits per cycle**, stores write memory here |
| `code/reference.py` | simple in-order interpreter used only to check results |
| `tests/` | test inputs + `run_tests.py`; `results/` = outputs for W=1,2,4 |
