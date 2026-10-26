# Report: multi-issue Tomasulo simulator

## 1. What I added / changed
Starting point: the single-issue Python Tomasulo simulator (`main/issue/exe/mem/wb/commit/init/print_status`).
Same module/stage structure was kept; the state handling inside was rewritten around one `Machine` object so
that several instructions per cycle (and speculation) can be handled correctly.

1. **Issue width 1..4 (in order)** - `issue.py`. Up to W instructions are fetched/decoded/renamed per cycle, in
   order. The group stops at the first structural hazard (ROB, RS or LSQ full) or after a predicted-taken branch.
   Sources are read from the RAT *before* the destination is renamed, so instructions in the same group see each
   other correctly (RAW inside a group). Issue width is read from the input file (`Issue width = N`, default 1) or `--issue-width`.
2. **Multiple WB per cycle** - `wb.py`: up to `cdb_width` (default = W) results are broadcast per cycle, oldest first
   (`CDB width = 1` gives the single-CDB machine).
3. **Multiple commits per cycle** - `commit.py`: up to `commit_width` (default = W), strictly in order.
4. **Branch prediction (the original code only stalled fetch at a branch)** - 1-bit predictor, 8-entry BTB indexed
   with the 3 LSBs of the word address of the PC (tag = PC). Prediction in ISSUE; resolution at the end of EX;
   on a misprediction in cycle n the RAT is restored from the checkpoint taken at the branch, all younger
   instructions are removed from ROB/RS/LSQ/FUs/CDB queue, and fetch restarts from the correct path in cycle **n+2**.
5. **Input/Output as in the assignment**: hardware table + ROB size + issue width + register/memory initialisation +
   program in one file; output = status table, register values (R0-R31, F0-F31), non-zero memory.
6. Fixed problems of the old code that break with width > 1 (hard-coded config, `PC.valid` stall, branch offset
   handled as bytes, Sd/commit special cases, no final register/memory dump).
7. **Verification**: `tests/run_tests.py` compares final registers/memory and instruction count with an in-order
   reference interpreter and checks pipeline invariants (stage order, <=W issues, <=commit-width commits, <=CDB
   broadcasts per cycle, in-order issue/commit, memory port never double-booked) for 8 hand-written tests x 4
   widths, CDB/commit variants and 400 random programs. Result: ALL OK.

## 2. Machine model (as implemented)
* Stages ISSUE, EX, MEM, WB, COMMIT. Issued in cycle c -> earliest EX c+1. Result broadcast in cycle t -> consumer
  can start EX in t+1; commit at the earliest in the cycle after WB (branch: after resolution).
* Integer adder unpipelined; FP adder and FP multiplier pipelined; loads/stores use a dedicated address adder.
  Branches use the integer ALU/RS. Integer R0 is hard-wired to 0.
* Load/store queue (program order). A load goes to memory when its address is known, all older stores have known
  addresses and none matches; if the nearest older matching store has its data the load is forwarded (1 cycle,
  no memory port). Loads leave the LSQ when they have data; stores write memory only at commit (and occupy the
  single, non-pipelined memory port for the memory latency) and are dequeued then.
* Execution is out of order (oldest ready first); issue and commit are in order.

## 3. Results (cycles / IPC, same program, different issue width; CDB = commit = W)
| test | what it tests | W=1 | W=2 | W=3 | W=4 |
|---|---|---|---|---|---|
| test1_loop | FP loop (Ld/Mult/Add/Sd, Bne, 3 iterations) | 57 / 0.44 | 52 / 0.48 | 51 / 0.49 | 51 / 0.49 |
| test2_independent | independent int + FP ops | 34 / 0.35 | 29 / 0.41 | 27 / 0.44 | 27 / 0.44 |
| test3_dependent | RAW chains, WAW/WAR via renaming | 46 / 0.24 | 43 / 0.26 | 42 / 0.26 | 42 / 0.26 |
| test4_memory | forwarding, disambiguation, dependent addresses | 52 / 0.23 | 55 / 0.22 | 55 / 0.22 | 55 / 0.22 |
| test5_branch_loop | array sum loop, 10 iterations | 55 / 0.75 | 51 / 0.80 | 50 / 0.82 | 49 / 0.84 |
| test6_branch_mix | Beq/Bne taken/not taken, wrong-path Sd/Ld | 23 / 0.39 | 20 / 0.45 | 19 / 0.47 | 18 / 0.50 |
| test7_alt_branch | alternating branch (1-bit predictor worst case) | 78 / 0.56 | 71 / 0.62 | 71 / 0.62 | 71 / 0.62 |
| test8_small_resources | ROB=4, 1 RS/unit, CDB=1, commit=1 | 37 / 0.24 | 36 / 0.25 | 36 / 0.25 | 36 / 0.25 |

Full per-instruction tables for W=1, 2, 4 are in `results/`.
Observations: wider issue helps most when work is independent (test2) or branchy (test6); it cannot help a
dependence chain (test3) or a loop bounded by the 15-20 cycle FP multiply and the single memory port (test1).
In test4 W=2 is 3 cycles *slower* than W=1: with W=2 the store reaches commit (and leaves the LSQ) before the
younger load looks for a forwarding match, so the load must wait for the memory port - a real memory-port /
timing effect, not a functional error (results are identical and verified).

## 4. What works / limitations
Works: everything listed in section 1 (verified). Limitations / assumptions:
* Branch offsets are in instructions (assignment: `PC+4+offset<<2`); the old `code.in` used `-12` with a byte-style
  conversion and was not a correct loop, so `test1_loop` uses `-8`. The example in the assignment sheet
  (`Bne R2,R3,-3` with R2!=R3) is an endless loop by construction; the simulator stops with an error after 200000 cycles.
* Wrong-path instructions are removed when the branch resolves; the fetch of cycle n (resolution cycle) is simply not
  performed, so the "squashed" statistic counts only wrong-path instructions that really were in the ROB.
* Memory is byte-addressed, one value per address; overlapping/misaligned accesses are not modelled
  (addresses are compared for equality). Stores to illegal addresses on the correct path raise an error.
* Default CDB width and commit width = issue width (the assignment text says "one CDB"; use `CDB width = 1` for that).
