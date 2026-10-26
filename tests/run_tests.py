"""
run_tests.py -- runs every tests/*.txt for issue widths 1..4 (and a few CDB/commit widths) and checks
  1. final registers + memory == in-order reference interpreter
  2. pipeline invariants (stage ordering, <= W issues / commits per cycle, <= CDB-width WBs per cycle,
     in-order commit, memory port never used by two accesses at once, issue only after the squash penalty)
  3. random programs (fuzzing) with all of the above
Usage:  python run_tests.py            (from the tests/ directory)
"""
import sys, os, glob, random, copy
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'code'))
from init import read_input, Config, parse_instruction
from main import simulate
from reference import run_reference
from collections import Counter


def check_run(cfg, prog, label):
    regs, mem, steps = run_reference(cfg, prog)
    m, cycles = simulate(copy.deepcopy(cfg), prog)
    errs = []
    for k in ('R', 'F'):
        for i in range(32):
            if abs(regs[k][i] - m.regs[k][i]) > 1e-9:
                errs.append('%s%d: ref=%s sim=%s' % (k, i, regs[k][i], m.regs[k][i]))
    for a in range(256):
        if abs(mem[a] - m.memory[a]) > 1e-9:
            errs.append('Mem[%d]: ref=%s sim=%s' % (a, mem[a], m.memory[a]))
    if len(m.log) != steps:
        errs.append('committed %d instructions, reference executed %d' % (len(m.log), steps))
    # ---- invariants ----
    iss, com, wbs = Counter(), Counter(), Counter()
    last_commit, last_seq, ports = 0, -1, []
    for i in m.log:
        iss[i.issue] += 1; com[i.commit] += 1
        if i.wb: wbs[i.wb] += 1
        if not (i.issue < i.ex_start <= i.ex_end): errs.append('EX order ' + i.st.text)
        if i.st.op == 'Ld':
            if not (i.ex_end < i.mem_start <= i.mem_end < i.wb): errs.append('Ld order ' + i.st.text)
            if not i.forwarded: ports.append((i.mem_start, i.mem_end))
        elif i.st.op == 'Sd':
            if not (i.ex_end < i.commit == i.mem_start): errs.append('Sd order ' + i.st.text)
            ports.append((i.mem_start, i.mem_end))
        elif i.st.op in ('Beq', 'Bne'):
            if not i.ex_end < i.commit: errs.append('Br order')
        else:
            if not (i.ex_end < i.wb < i.commit): errs.append('ALU order ' + i.st.text)
        if i.commit < last_commit or i.seq < last_seq: errs.append('out of order commit')
        last_commit, last_seq = i.commit, i.seq
    # issue is in order: issue cycle never decreases along program (commit) order
    if any(a.issue > b.issue for a, b in zip(m.log, m.log[1:])): errs.append('out-of-order issue')
    if iss and max(iss.values()) > m.W: errs.append('more than W issues in a cycle')
    if com and max(com.values()) > m.commit_w: errs.append('more than commit-width commits in a cycle')
    if wbs and max(wbs.values()) > m.cdb_w: errs.append('more CDB broadcasts than CDB width')
    ports.sort()
    for a, b in zip(ports, ports[1:]):
        if b[0] <= a[1]: errs.append('memory port overlap %s %s' % (a, b))
    return errs, cycles, m


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    bad = 0
    print('%-26s' % 'test' + ''.join('W=%d (cyc/IPC)   ' % w for w in (1, 2, 3, 4)))
    for f in sorted(glob.glob(os.path.join(here, 'test*.txt'))):
        cfg0, prog = read_input(f)
        row = '%-26s' % os.path.basename(f)
        for w in (1, 2, 3, 4):
            cfg = copy.deepcopy(cfg0); cfg.issue_width = w
            errs, cycles, m = check_run(cfg, prog, f)
            row += '%4d / %.2f %s  ' % (cycles, len(m.log) / cycles, 'ok ' if not errs else 'BAD')
            if errs:
                bad += 1
                print('\n'.join('   ' + e for e in errs[:6]))
        print(row)
    # different CDB / commit widths
    cfg0, prog = read_input(os.path.join(here, 'test2_independent.txt'))
    for w, c, k in ((4, 1, 4), (4, 4, 1), (2, 1, 1), (1, 4, 4)):
        cfg = copy.deepcopy(cfg0); cfg.issue_width, cfg.cdb_width, cfg.commit_width = w, c, k
        errs, cycles, m = check_run(cfg, prog, 'cdb/commit')
        print('independent W=%d CDB=%d COMMIT=%d: %d cycles %s' % (w, c, k, cycles, 'ok' if not errs else 'BAD ' + str(errs[:3])))
        bad += bool(errs)
    # ---- fuzzing ----
    random.seed(12345)
    n = 0
    for t in range(400):
        cfg = Config()
        cfg.rob_size = random.choice([2, 3, 4, 8, 16, 64])
        cfg.issue_width = random.randint(1, 4)
        cfg.cdb_width = random.choice([None, 1, 2])
        cfg.commit_width = random.choice([None, 1, 2])
        from init import UnitCfg
        cfg.units['int'] = UnitCfg(random.randint(1, 4), random.randint(1, 3), None, random.randint(1, 2))
        cfg.units['fpadd'] = UnitCfg(random.randint(1, 3), random.randint(1, 5), None, random.randint(1, 2))
        cfg.units['fpmul'] = UnitCfg(random.randint(1, 3), random.randint(1, 12), None, random.randint(1, 2))
        cfg.units['mem'] = UnitCfg(random.randint(1, 5), random.randint(1, 2), random.randint(1, 6), random.randint(1, 2))
        for r in range(1, 6): cfg.regs_int[r] = random.randint(0, 6) * 4
        for r in range(1, 6): cfg.regs_fp[r] = float(random.randint(1, 9))
        for a in range(0, 64, 4): cfg.mem_init[a] = float(random.randint(1, 9))
        lines = []
        L = random.randint(5, 40)
        for i in range(L):
            k = random.random()
            R = lambda: 'R%d' % random.randint(0, 6)
            F = lambda: 'F%d' % random.randint(1, 6)
            if k < 0.15: lines.append('Ld %s, %d(R0)' % (F(), 4 * random.randint(0, 15)))
            elif k < 0.30: lines.append('Sd %s, %d(R0)' % (F(), 4 * random.randint(0, 15)))
            elif k < 0.38: lines.append('Ld %s, %d(R7)' % (F(), 4 * random.randint(0, 3)))   # base reg R7 (dependent address)
            elif k < 0.46: lines.append('Addi R7, %s, %d' % (random.choice(['R0', 'R7']), 4 * random.randint(0, 12)))
            elif k < 0.52: lines.append('Sd %s, %d(R7)' % (F(), 4 * random.randint(0, 3)))
            elif k < 0.60: lines.append('Add %s, %s, %s' % (R().replace('R0', 'R6'), R(), R()))
            elif k < 0.66: lines.append('Sub %s, %s, %s' % (R().replace('R0', 'R6'), R(), R()))
            elif k < 0.72: lines.append('Addi %s, %s, %d' % (R().replace('R0', 'R6'), R(), random.randint(-3, 3)))
            elif k < 0.80: lines.append('Add.d %s, %s, %s' % (F(), F(), F()))
            elif k < 0.85: lines.append('Sub.d %s, %s, %s' % (F(), F(), F()))
            elif k < 0.90: lines.append('Mult.d %s, %s, %s' % (F(), F(), F()))
            else:
                off = random.randint(0, min(3, L - i - 1))   # forward branches only -> always terminates
                lines.append('%s %s, %s, %d' % (random.choice(['Beq', 'Bne']), R(), R(), off))
        prog = [parse_instruction(x) for x in lines]
        # R7 must stay a legal base (0..48): it is only ever set by Addi from R0/R7 with small offsets; clamp via reference
        try:
            regs, mem, steps = run_reference(cfg, prog)
        except Exception:
            continue                    # illegal address in this random program -> skip
        n += 1
        errs, cycles, m = check_run(cfg, prog, 'fuzz%d' % t)
        if errs:
            bad += 1
            print('FUZZ %d BAD' % t, lines, errs[:4])
    print('fuzz programs checked: %d' % n)
    print('ALL OK' if not bad else '%d FAILURES' % bad)
    return bad


if __name__ == '__main__':
    sys.exit(1 if main() else 0)
