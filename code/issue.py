
from init import Ins, Opnd, BTB_SIZE


def read_operand(m, kind, idx):
    if kind == 'R' and idx == 0:
        return Opnd(None, 0)                       
    prod = m.rat[kind][idx]
    if prod is None:
        return Opnd(None, m.regs[kind][idx])      
    return Opnd(prod, None)                        


def predict(m, pc):
    e = m.btb[pc % BTB_SIZE]
    if e is not None and e[0] == pc and e[1]:
        return True, e[2]
    return False, pc + 1


def issue(m, cycle):
    if cycle < m.fetch_resume:                     
        return
    for _ in range(m.W):
        pc = m.fetch_pc
        if not 0 <= pc < len(m.prog):
            break
        st = m.prog[pc]
        if len(m.rob) >= m.cfg.rob_size:
            break
        if st.cls == 'mem':
            if len(m.lsq) >= m.cfg.units['mem'].rs:
                break
        elif len(m.rs[st.cls]) >= m.cfg.units[st.cls].rs:
            break

        ins = Ins(m.seq, pc, st)
        m.seq += 1
        ins.issue = cycle
        if st.op in ('Ld', 'Sd'):
            ins.src1 = read_operand(m, 'R', st.rs[1])                  
            if st.op == 'Sd':
                ins.src2 = read_operand(m, 'F', st.rd[1])              
        elif st.op == 'Addi':
            ins.src1 = read_operand(m, 'R', st.rs[1])
            ins.src2 = Opnd(None, st.imm)
        else:
            ins.src1 = read_operand(m, st.rs[0], st.rs[1])
            ins.src2 = read_operand(m, st.rt[0], st.rt[1])
        if st.op not in ('Sd', 'Beq', 'Bne'):
            kind, idx = st.rd
            if not (kind == 'R' and idx == 0):
                ins.dest = (kind, idx)
                m.rat[kind][idx] = ins
        m.rob.append(ins)
        if st.cls == 'mem':
            m.lsq.append(ins)
        else:
            m.rs[st.cls].append(ins)

        if st.op in ('Beq', 'Bne'):
            ins.pred_taken, ins.pred_next = predict(m, pc)
            ins.rat_ckpt = ({k: list(v) for k, v in m.rat.items()})   
            m.fetch_pc = ins.pred_next
            m.stats['branches'] += 1
            if ins.pred_taken:
                break                                                 
        else:
            m.fetch_pc = pc + 1
