
import sys
import argparse
from init import read_input, Machine
from issue import issue
from exe import exe
from mem import mem
from wb import wb
from commit import commit
from print_status import print_table, print_regs, print_mem, print_stats


def simulate(cfg, prog, max_cycles=200000):
    m = Machine(cfg, prog)
    cycle = 1
    while not m.done():
        if cycle > max_cycles:
            raise RuntimeError('no termination after %d cycles (infinite loop in the program?)' % max_cycles)
        commit(m, cycle)       
        wb(m, cycle)           
        mem(m, cycle)          
        exe(m, cycle)          
        issue(m, cycle)        
        cycle += 1
    return m, cycle - 1


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('input', nargs='?', default='../tests/test1_loop.txt')
    ap.add_argument('--issue-width', type=int)
    ap.add_argument('--cdb-width', type=int)
    ap.add_argument('--commit-width', type=int)
    ap.add_argument('--max-cycles', type=int, default=200000)
    a = ap.parse_args(argv)
    cfg, prog = read_input(a.input)
    if a.issue_width is not None: cfg.issue_width = a.issue_width
    if a.cdb_width is not None: cfg.cdb_width = a.cdb_width
    if a.commit_width is not None: cfg.commit_width = a.commit_width
    if not 1 <= cfg.issue_width <= 4:
        sys.exit('issue width must be 1..4')
    m, cycles = simulate(cfg, prog, a.max_cycles)
    print_table(m)
    print_regs(m)
    print_mem(m)
    print_stats(m, cycles)


if __name__ == '__main__':
    main()
