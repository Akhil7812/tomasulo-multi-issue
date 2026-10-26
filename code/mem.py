

def finish_port(m, cycle):
    ld = m.port_ins
    if ld is not None and m.port_finish == cycle:
        ld.mem_end = cycle
        a = ld.addr
        ld.result = m.memory[a] if 0 <= a < len(m.memory) else 0      
        m.pending.append((cycle + 1, ld))
        m.lsq.remove(ld)
        m.port_ins = None; m.port_finish = None


def check_older_stores(m, ld, cycle):
    """returns ('free', None) | ('wait', None) | ('fwd', store)"""
    older = [x for x in m.lsq if x.seq < ld.seq and x.st.op == 'Sd']
    for st in reversed(older):                                   
        if st.addr_cycle is None or st.addr_cycle >= cycle:
            return 'wait', None                                   
        if st.addr == ld.addr:
            return ('fwd', st) if st.src2.ready(cycle) else ('wait', None)
    return 'free', None


def mem(m, cycle):
    finish_port(m, cycle)
    for ld in [x for x in m.lsq if x.st.op == 'Ld']:
        if ld.mem_start is not None or ld.addr_cycle is None or ld.addr_cycle >= cycle:
            continue
        what, st = check_older_stores(m, ld, cycle)
        if what == 'fwd':
            ld.mem_start = ld.mem_end = cycle
            ld.forwarded = True
            ld.result = st.src2.get()
            m.pending.append((cycle + 1, ld))
            m.lsq.remove(ld)
        elif what == 'free' and m.port_free <= cycle and m.port_ins is None:
            L = m.cfg.units['mem'].mem
            ld.mem_start = cycle
            m.port_ins, m.port_finish = ld, cycle + L - 1
            m.port_free = cycle + L
    finish_port(m, cycle)                                        
