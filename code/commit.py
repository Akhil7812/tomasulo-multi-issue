
def commit(m, cycle):
    for _ in range(m.commit_w):
        if not m.rob:
            return
        h = m.rob[0]
        op = h.st.op
        if op in ('Beq', 'Bne'):
            if h.resolved is None or h.resolved >= cycle:
                return
        elif op == 'Sd':
            if h.addr_cycle is None or h.addr_cycle >= cycle or not h.src2.ready(cycle) or m.port_free > cycle:
                return
            if not 0 <= h.addr < len(m.memory):
                raise RuntimeError('store to illegal address %d (%s)' % (h.addr, h.st.text))
            L = m.cfg.units['mem'].mem
            m.memory[h.addr] = h.src2.get()
            h.mem_start, h.mem_end = cycle, cycle + L - 1
            m.port_free = cycle + L
            m.lsq.remove(h)
        else:
            if h.wb is None or h.wb >= cycle:
                return
            if h.dest is not None:
                k, i = h.dest
                m.regs[k][i] = h.result
                if m.rat[k][i] is h:
                    m.rat[k][i] = None
        m.rob.popleft()
        h.commit = cycle
        h.committed = True
        m.log.append(h)
