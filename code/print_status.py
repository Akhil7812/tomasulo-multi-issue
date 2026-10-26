

def fmt(v):
    if isinstance(v, float):
        return '%.1f' % v if v == int(v) and abs(v) < 1e15 else '%.10g' % v
    return str(v)


def rng(a, b):
    if a is None:
        return ''
    return str(a) if (b is None or a == b) else '%d-%d' % (a, b)


def print_table(m):
    w = 28
    print('%-*s%-9s%-9s%-9s%-9s%s' % (w, '', 'ISSUE', 'EX', 'MEM', 'WB', 'COMMIT'))
    for i in m.log:
        print('%-*s%-9s%-9s%-9s%-9s%s' % (w, i.st.text, i.issue, rng(i.ex_start, i.ex_end),
                                         rng(i.mem_start, i.mem_end), fmt(i.wb) if i.wb else '', i.commit))


def print_regs(m):
    print('\nREGISTER VALUES\n')
    for k, name in (('R', 'R'), ('F', 'F')):
        for base in (0, 16):
            print('      ' + ''.join('%-9s' % ('%s%d' % (name, base + j)) for j in range(16)))
            print('value:' + ''.join('%-9s' % fmt(m.regs[k][base + j]) for j in range(16)))
        print()


def print_mem(m):
    print('NON-ZERO MEMORY VALUES\n')
    print('%-12s%s' % ('Addresses', 'Values'))
    for a, v in enumerate(m.memory):
        if v != 0:
            print('%-12d%s' % (a, fmt(v)))


def print_stats(m, cycles):
    n = len(m.log)
    print('\nSTATISTICS: issue width=%d cdb width=%d commit width=%d' % (m.W, m.cdb_w, m.commit_w))
    print('  cycles=%d committed=%d IPC=%.3f  branches(issued)=%d mispredicted=%d squashed=%d'
          % (cycles, n, n / cycles if cycles else 0, m.stats['branches'], m.stats['mispredicts'], m.stats['squashed']))
