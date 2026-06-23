# RA4 — Linker / Codificador ARM → Intel HEX
#
# Converte o arquivo .s gerado pelo compilador ARMv7 em formato Intel HEX.
# Implementa um montador de dois passos (two-pass assembler):
#   Passo 1: percorre as linhas, atribui endereços e constrói a tabela
#            de símbolos (labels → endereços).
#   Passo 2: codifica cada instrução em 32 bits usando os endereços
#            resolvidos, gerando o stream de bytes.
# O resultado é emitido no formato Intel HEX (IHEX), que pode ser
# carregado diretamente no CPUlator DE1-SoC.
#
# Endereço de carga padrão: 0x00000000 (segmento .text).
# Endereço do segmento .data: logo após o .text (alinhado a 4 bytes).
#
# Instruções suportadas (subconjunto usado pelo gerador ARMv7):
#   Data processing: MOV, MVN, ADD, SUB, RSB, AND, ORR, EOR, BIC,
#                    CMP, TST, MUL, SUBS, ADDS, MOVMI, MOVEQ, MOVNE
#   Branches:        B, BL, BEQ, BNE, BGT, BGE, BLT, BLE, BX
#   Mem acesso:      LDR (immediate/reg), STR (immediate/reg),
#                    VLDR.F64, VSTR.F64, LDRB
#   VFP:             VMOV, VADD.F64, VSUB.F64, VMUL.F64, VDIV.F64,
#                    VCVT.S32.F64, VCVT.F64.S32, VCMP.F64, VMRS,
#                    VMOV.F64
#   Stack:           PUSH, POP
#   Misc:            RSBMI, RSBNE, EORMI, LSL shift suffix

import re
import struct

# Endereço base do segmento .text
BASE_TEXT = 0x00000000

# Códigos de condição ARM (bits 31-28)
_COND = {
    "EQ": 0x0, "NE": 0x1, "GE": 0xA, "LT": 0xB,
    "GT": 0xC, "LE": 0xD, "AL": 0xE, "MI": 0x4,
    "": 0xE,  # sem sufixo = AL
}

# Opcodes de data-processing (bits 24-21)
_DP_OPC = {
    "AND": 0x0, "EOR": 0x1, "SUB": 0x2, "RSB": 0x3,
    "ADD": 0x4, "ADC": 0x5, "SBC": 0x6, "RSC": 0x7,
    "TST": 0x8, "TEQ": 0x9, "CMP": 0xA, "CMN": 0xB,
    "ORR": 0xC, "MOV": 0xD, "BIC": 0xE, "MVN": 0xF,
}

# Números de registradores
_REG = {
    "r0": 0, "r1": 1, "r2": 2, "r3": 3, "r4": 4, "r5": 5,
    "r6": 6, "r7": 7, "r8": 8, "r9": 9, "r10": 10, "r11": 11,
    "r12": 12, "r13": 13, "r14": 14, "r15": 15,
    "sp": 13, "lr": 14, "pc": 15,
    # VFP single
    "s0": 0, "s2": 2,
    # FPSCR alias
    "apsr_nzcv": 15,
}

# VFP double registers
_DREG = {f"d{i}": i for i in range(32)}
# VFP single registers
_SREG = {f"s{i}": i for i in range(32)}


def _parse_imm(s: str) -> int:
    s = s.strip()
    if s.startswith("0x") or s.startswith("0X"):
        return int(s, 16)
    if s.startswith("#"):
        return _parse_imm(s[1:])
    return int(s, 0)


def _encode_imm8r(value: int) -> tuple[int, int] | None:
    """Tenta codificar `value` como imm8 rotacionado (ARM imm12 format).
    Retorna (rot, imm8) ou None se não for possível."""
    value &= 0xFFFFFFFF
    for rot in range(0, 32, 2):
        imm8 = (value >> rot) | (value << (32 - rot))
        imm8 &= 0xFF
        check = (imm8 >> rot) | (imm8 << (32 - rot))
        check &= 0xFFFFFFFF
        if check == value:
            return (rot >> 1), imm8
    return None


def _encode_dp_imm(cond: int, opc: int, s: int, rn: int, rd: int, imm: int) -> int:
    """Codifica instrução data-processing com operando imediato."""
    enc = _encode_imm8r(imm)
    if enc is None:
        # fallback: tenta MOV alto/baixo em dois passos (simplificação)
        enc = (0, imm & 0xFF)
    rot, imm8 = enc
    return (cond << 28) | (1 << 25) | (opc << 21) | (s << 20) | (rn << 16) | (rd << 12) | (rot << 8) | imm8


def _encode_dp_reg(cond: int, opc: int, s: int, rn: int, rd: int, rm: int, shift_type: int = 0, shift_amt: int = 0) -> int:
    return (cond << 28) | (0 << 25) | (opc << 21) | (s << 20) | (rn << 16) | (rd << 12) | (shift_amt << 7) | (shift_type << 5) | rm


def _encode_mul(cond: int, s: int, rd: int, rs: int, rm: int) -> int:
    return (cond << 28) | (rd << 16) | (0 << 12) | (rs << 8) | (0b1001 << 4) | rm | (s << 20)


def _encode_branch(cond: int, link: int, offset_bytes: int) -> int:
    offset = ((offset_bytes - 8) >> 2) & 0x00FFFFFF
    return (cond << 28) | (0b101 << 25) | (link << 24) | offset


def _encode_bx(cond: int, rm: int) -> int:
    return (cond << 28) | 0x012FFF10 | rm


def _encode_ldr_str_imm(cond: int, p: int, u: int, b: int, w: int, load: int, rn: int, rd: int, offset: int) -> int:
    return (cond << 28) | (0b01 << 26) | (p << 24) | (u << 23) | (b << 22) | (w << 21) | (load << 20) | (rn << 16) | (rd << 12) | (offset & 0xFFF)


def _encode_ldm_stm(cond: int, p: int, u: int, s: int, w: int, load: int, rn: int, reg_list: int) -> int:
    return (cond << 28) | (0b100 << 25) | (p << 24) | (u << 23) | (s << 22) | (w << 21) | (load << 20) | (rn << 16) | (reg_list & 0xFFFF)


def _reg_list_bits(regs_str: str) -> int:
    """Converte '{r0, r4, lr}' em bitmask de registradores."""
    bits = 0
    regs_str = regs_str.strip().strip("{}").strip()
    for r in regs_str.split(","):
        r = r.strip().lower()
        if r in _REG:
            bits |= (1 << _REG[r])
    return bits


def _vfp_dreg(name: str) -> int:
    name = name.strip().lower()
    return _DREG.get(name, 0)


def _vfp_sreg(name: str) -> int:
    name = name.strip().lower()
    return _SREG.get(name, 0)


def _encode_vfp_mem(cond: int, load: int, rn: int, dd: int, offset8: int) -> int:
    """VLDR/VSTR.F64 — coprocessador CP11 (double)."""
    # cond 1101 U D01 1011 Rn Dd 1011 offset8
    d_hi = (dd >> 4) & 1
    d_lo = dd & 0xF
    u = 1 if offset8 >= 0 else 0
    off = abs(offset8) & 0xFF
    return (cond << 28) | (0b1101 << 24) | (u << 23) | (d_hi << 22) | (0b01 << 20) | (load << 20) | (rn << 16) | (d_lo << 12) | (0b1011 << 8) | off


def _encode_vldr_f64(cond: int, rn: int, dd: int, offset_bytes: int = 0) -> int:
    d_hi = (dd >> 4) & 1
    d_lo = dd & 0xF
    u = 1 if offset_bytes >= 0 else 0
    off8 = (abs(offset_bytes) // 4) & 0xFF
    return (cond << 28) | (0b1101 << 24) | (u << 23) | (d_hi << 22) | (0b011011 << 16) | (rn << 16) | (d_lo << 12) | (0b1011 << 8) | off8


def _encode_vstr_f64(cond: int, rn: int, dd: int, offset_bytes: int = 0) -> int:
    d_hi = (dd >> 4) & 1
    d_lo = dd & 0xF
    u = 1 if offset_bytes >= 0 else 0
    off8 = (abs(offset_bytes) // 4) & 0xFF
    return (cond << 28) | (0b1101 << 24) | (u << 23) | (d_hi << 22) | (0b010011 << 16) | (rn << 16) | (d_lo << 12) | (0b1011 << 8) | off8


def _encode_vmov_to_d(cond: int, rt: int, rt2: int, dm: int) -> int:
    """VMOV dm, rt, rt2 — transfere dois ARM regs para d reg."""
    m_hi = (dm >> 4) & 1
    m_lo = dm & 0xF
    return (cond << 28) | 0x00C00B10 | (rt2 << 16) | (rt << 12) | (m_hi << 5) | m_lo


def _encode_vmov_from_d(cond: int, rt: int, rt2: int, dm: int) -> int:
    """VMOV rt, rt2, dm — transfere d reg para dois ARM regs."""
    m_hi = (dm >> 4) & 1
    m_lo = dm & 0xF
    return (cond << 28) | 0x00F00B10 | (rt2 << 16) | (rt << 12) | (m_hi << 5) | m_lo


def _encode_vmov_arm_vfp(cond: int, to_arm: int, vn: int, rt: int) -> int:
    """VMOV rt, sn  ou  VMOV sn, rt — mover entre ARM e VFP single."""
    n_lo = vn & 0xF
    n_hi = (vn >> 4) & 1
    return (cond << 28) | (0b11100 << 23) | (n_lo << 16) | (rt << 12) | (0b1010 << 8) | (n_hi << 7) | (to_arm << 20) | (1 << 4)


def _encode_vcvt_f64_s32(cond: int, dd: int, sm: int) -> int:
    """VCVT.F64.S32 dd, sm"""
    d_hi = (dd >> 4) & 1
    d_lo = dd & 0xF
    m_hi = (sm >> 4) & 1
    m_lo = sm & 0xF
    return (cond << 28) | 0x0EB80BC0 | (d_hi << 22) | (d_lo << 12) | (m_hi << 5) | m_lo


def _encode_vcvt_s32_f64(cond: int, sd: int, dm: int) -> int:
    """VCVT.S32.F64 sd, dm"""
    d_hi = (sd >> 4) & 1
    d_lo = sd & 0xF
    m_hi = (dm >> 4) & 1
    m_lo = dm & 0xF
    return (cond << 28) | 0x0EBD0B40 | (d_hi << 22) | (d_lo << 12) | (m_hi << 5) | m_lo


def _encode_vfp_bin(cond: int, opc4: int, dd: int, dn: int, dm: int) -> int:
    """VADD/VSUB/VMUL/VDIV.F64"""
    d_hi = (dd >> 4) & 1
    d_lo = dd & 0xF
    n_hi = (dn >> 4) & 1
    n_lo = dn & 0xF
    m_hi = (dm >> 4) & 1
    m_lo = dm & 0xF
    return (cond << 28) | (0b11100 << 23) | (opc4 << 20) | (n_lo << 16) | (d_hi << 22) | (d_lo << 12) | (0b1011 << 8) | (n_hi << 7) | (m_hi << 5) | m_lo


def _encode_vcmp_f64(cond: int, dd: int, dm: int) -> int:
    """VCMP.F64 dd, dm"""
    d_hi = (dd >> 4) & 1
    d_lo = dd & 0xF
    m_hi = (dm >> 4) & 1
    m_lo = dm & 0xF
    return (cond << 28) | 0x0EB40B40 | (d_hi << 22) | (d_lo << 12) | (m_hi << 5) | m_lo


def _encode_vmrs(cond: int) -> int:
    """VMRS APSR_nzcv, FPSCR"""
    return (cond << 28) | 0x0EF10A10 | (15 << 12)


def _encode_vmov_f64(cond: int, dd: int, dm: int) -> int:
    """VMOV.F64 dd, dm"""
    d_hi = (dd >> 4) & 1
    d_lo = dd & 0xF
    m_hi = (dm >> 4) & 1
    m_lo = dm & 0xF
    return (cond << 28) | 0x0EB00B40 | (d_hi << 22) | (d_lo << 12) | (m_hi << 5) | m_lo


# ---------------------------------------------------------------------------
# Tokenizador de linhas de assembly
# ---------------------------------------------------------------------------

_RE_LABEL = re.compile(r'^(\w+)\s*:\s*(.*)$')
_RE_COMMENT = re.compile(r'@.*$')
_RE_DIRECTIVE = re.compile(r'^\.(syntax|cpu|fpu|global|text|data|byte|double|word|balign|align|space|ltorg)\b', re.I)


def _strip_line(line: str) -> str:
    """Remove comentários ARM (@) e espaço em branco."""
    line = _RE_COMMENT.sub('', line)
    return line.strip()


def _parse_args(args_str: str) -> list[str]:
    """Divide os argumentos por vírgula, preservando conteúdo entre {} e [].

    Os colchetes precisam ser protegidos porque endereçamentos como
    ``[r1, #4]`` ou ``[r1, r3, LSL #2]`` contêm vírgulas internas que NÃO
    separam operandos.
    """
    result = []
    depth = 0
    current = []
    for ch in args_str:
        if ch in '{[':
            depth += 1
            current.append(ch)
        elif ch in '}]':
            depth -= 1
            current.append(ch)
        elif ch == ',' and depth == 0:
            result.append(''.join(current).strip())
            current = []
        else:
            current.append(ch)
    if current:
        result.append(''.join(current).strip())
    return result


# ---------------------------------------------------------------------------
# Estrutura de instrução pré-processada
# ---------------------------------------------------------------------------

class _Instr:
    __slots__ = ('label', 'mnemonic', 'args', 'raw', 'address', 'encoded',
                 'is_directive', 'directive', 'directive_args', 'is_ldr_pseudo',
                 'ldr_reg', 'ldr_label_or_imm', 'pool_entry')

    def __init__(self):
        self.label = None
        self.mnemonic = None
        self.args = []
        self.raw = ''
        self.address = 0
        self.encoded = None       # int (32-bit word) or bytes
        self.is_directive = False
        self.directive = None
        self.directive_args = ''
        self.is_ldr_pseudo = False
        self.ldr_reg = None
        self.ldr_label_or_imm = None
        self.pool_entry = None    # label gerado para o literal pool


# ---------------------------------------------------------------------------
# Passo 1: parse e atribuição de endereços
# ---------------------------------------------------------------------------

def _pass1(asm_text: str):
    """Retorna (instrucoes, symbols, data_bytes, data_labels)."""
    lines = asm_text.splitlines()
    instrucoes: list[_Instr] = []
    symbols: dict[str, int] = {}
    data_section = False
    addr = BASE_TEXT
    pool_counter = [0]
    pool_map: dict[str, str] = {}   # value_str -> pool_label
    pool_labels: list[tuple[str, str]] = []  # (label, value_str) to emit at end of .text

    # Primeira varredura: separa diretivas, labels, instruções
    for raw_line in lines:
        line = _strip_line(raw_line)
        if not line:
            continue

        instr = _Instr()
        instr.raw = raw_line

        # Verifica label no início
        m = _RE_LABEL.match(line)
        if m:
            instr.label = m.group(1)
            line = _strip_line(m.group(2))
            if not line:
                # linha só com label: registraremos o endereço depois
                instrucoes.append(instr)
                continue

        # Diretiva de seção
        if line.lower() == '.text':
            data_section = False
            instr.is_directive = True
            instr.directive = '.text'
            instrucoes.append(instr)
            continue
        if line.lower() == '.data':
            data_section = True
            instr.is_directive = True
            instr.directive = '.data'
            instrucoes.append(instr)
            continue

        if _RE_DIRECTIVE.match(line):
            instr.is_directive = True
            parts = line.split(None, 1)
            instr.directive = parts[0].lower()
            instr.directive_args = parts[1] if len(parts) > 1 else ''
            instrucoes.append(instr)
            continue

        # Instrução normal
        parts = line.split(None, 1)
        mnem = parts[0].upper()
        args_str = parts[1] if len(parts) > 1 else ''

        # LDR rX, =label_ou_imm  (pseudo-instrução)
        ldr_pseudo = re.match(r'^LDR\s+(r\d+|r1[0-5]),\s*=(\S+)', line, re.I)
        if ldr_pseudo:
            instr.is_ldr_pseudo = True
            instr.ldr_reg = ldr_pseudo.group(1).lower()
            instr.ldr_label_or_imm = ldr_pseudo.group(2)
            val_key = instr.ldr_label_or_imm
            if val_key not in pool_map:
                plbl = f'__pool_{pool_counter[0]}'
                pool_counter[0] += 1
                pool_map[val_key] = plbl
                pool_labels.append((plbl, val_key))
            instr.pool_entry = pool_map[val_key]
            instr.mnemonic = 'LDR'
            instrucoes.append(instr)
            continue

        instr.mnemonic = mnem
        instr.args = _parse_args(args_str)
        instrucoes.append(instr)

    # Segunda varredura: atribuir endereços e construir tabela de símbolos
    # Inserir os pools de literais no final do segmento .text (antes do .data)
    # Encontrar posição de inserção (logo antes de '.data')
    data_pos = None
    for i, ins in enumerate(instrucoes):
        if ins.is_directive and ins.directive == '.data':
            data_pos = i
            break

    if pool_labels:
        pool_instrs = []
        for plbl, val_str in pool_labels:
            p = _Instr()
            p.label = plbl
            p.is_directive = True
            p.directive = '.word'
            p.directive_args = val_str
            pool_instrs.append(p)
        if data_pos is not None:
            instrucoes[data_pos:data_pos] = pool_instrs
        else:
            instrucoes.extend(pool_instrs)

    # Terceira varredura: atribuição de endereços
    addr = BASE_TEXT
    data_section = False
    data_addr = None

    for instr in instrucoes:
        if instr.is_directive:
            if instr.directive == '.text':
                data_section = False
            elif instr.directive == '.data':
                data_section = True
                # alinha a 8 bytes
                if addr % 8 != 0:
                    addr += 8 - (addr % 8)
                data_addr = addr
            elif instr.directive in ('.double',):
                if instr.label:
                    symbols[instr.label] = addr
                addr += 8  # 64 bits
            elif instr.directive == '.byte':
                if instr.label:
                    symbols[instr.label] = addr
                count = len(instr.directive_args.split(','))
                addr += count
            elif instr.directive == '.word':
                if instr.label:
                    symbols[instr.label] = addr
                addr += 4
            elif instr.directive == '.space':
                if instr.label:
                    symbols[instr.label] = addr
                try:
                    addr += _parse_imm(instr.directive_args.split(',')[0].strip())
                except (ValueError, IndexError):
                    pass
            elif instr.directive == '.balign':
                try:
                    n = _parse_imm(instr.directive_args.strip())
                    if n > 0 and addr % n != 0:
                        addr += n - (addr % n)
                except ValueError:
                    pass
                if instr.label:
                    symbols[instr.label] = addr
            elif instr.directive in ('.syntax', '.cpu', '.fpu', '.global', '.align'):
                pass
        else:
            instr.address = addr
            if instr.label:
                symbols[instr.label] = addr
            if not instr.is_directive:
                if instr.mnemonic:
                    addr += 4  # todas as instruções ARM são 4 bytes

    return instrucoes, symbols


# ---------------------------------------------------------------------------
# Passo 2: codificação
# ---------------------------------------------------------------------------

def _get_reg(name: str) -> int:
    return _REG.get(name.strip().lower(), 0)


def _get_dreg(name: str) -> int:
    return _DREG.get(name.strip().lower(), 0)


def _get_sreg(name: str) -> int:
    return _SREG.get(name.strip().lower(), 0)


def _mnem_cond(mnem: str) -> tuple[str, int]:
    """Separa mnemônico da condição. Ex.: 'MOVMI' -> ('MOV', 4)"""
    for cond_name, cond_val in _COND.items():
        if cond_name and mnem.endswith(cond_name):
            base = mnem[:-len(cond_name)]
            if base:
                return base, cond_val
    return mnem, 0xE  # AL


def _encode_instr(instr: _Instr, symbols: dict[str, int]) -> int | None:
    """Codifica uma instrução ARM para 32 bits. Retorna None para pseudo/label-only."""
    if instr.is_directive or not instr.mnemonic:
        return None
    if instr.is_ldr_pseudo:
        return _encode_ldr_pseudo(instr, symbols)

    mnem = instr.mnemonic
    args = instr.args
    addr = instr.address

    m_base, cond = _mnem_cond(mnem)

    # --- MOVW / MOVT (ARMv7, imediato de 16 bits) ---
    # MOVW: cond 0011 0000 imm4 Rd imm12   (imm16 = imm4:imm12, zera [31:16])
    # MOVT: cond 0011 0100 imm4 Rd imm12   (escreve só [31:16])
    if m_base == 'MOVW':
        rd = _get_reg(args[0])
        imm16 = _parse_imm(args[1]) & 0xFFFF
        return (cond << 28) | 0x03000000 | (((imm16 >> 12) & 0xF) << 16) | (rd << 12) | (imm16 & 0xFFF)
    if m_base == 'MOVT':
        rd = _get_reg(args[0])
        imm16 = _parse_imm(args[1]) & 0xFFFF
        return (cond << 28) | 0x03400000 | (((imm16 >> 12) & 0xF) << 16) | (rd << 12) | (imm16 & 0xFFF)

    # --- MOV / MVN ---
    if m_base in ('MOV', 'MVN'):
        opc = _DP_OPC[m_base]
        s = 1 if mnem.endswith('S') and not mnem.endswith('TS') else 0
        rd = _get_reg(args[0])
        if len(args) >= 2 and args[1].startswith('#'):
            imm = _parse_imm(args[1])
            return _encode_dp_imm(cond, opc, s, 0, rd, imm & 0xFFFFFFFF)
        elif len(args) >= 2:
            # check for shift suffix: MOV r0, r1, LSL #n
            rm = _get_reg(args[1])
            shift_type, shift_amt = 0, 0
            if len(args) >= 3 and args[2].upper().startswith('LSL'):
                shift_type = 0
                shift_amt = _parse_imm(args[2].split('#')[1]) if '#' in args[2] else 0
            return _encode_dp_reg(cond, opc, s, 0, rd, rm, shift_type, shift_amt)

    # --- ADD / SUB / AND / ORR / EOR / BIC / RSB ---
    if m_base in ('ADD', 'SUB', 'AND', 'ORR', 'EOR', 'BIC', 'RSB', 'ADC',
                  'ADDS', 'SUBS'):
        base = m_base.rstrip('S')
        opc = _DP_OPC[base]
        s = 1 if m_base.endswith('S') else 0
        rd = _get_reg(args[0])
        rn = _get_reg(args[1])
        if len(args) >= 3 and args[2].startswith('#'):
            imm = _parse_imm(args[2])
            return _encode_dp_imm(cond, opc, s, rn, rd, imm & 0xFFFFFFFF)
        elif len(args) >= 3:
            rm = _get_reg(args[2])
            shift_type, shift_amt = 0, 0
            if len(args) >= 4 and 'LSL' in args[3].upper():
                shift_type = 0
                shift_amt = _parse_imm(args[3].split('#')[1]) if '#' in args[3] else 0
            return _encode_dp_reg(cond, opc, s, rn, rd, rm, shift_type, shift_amt)

    # --- CMP / TST / TEQ ---
    if m_base in ('CMP', 'TST', 'TEQ'):
        opc = _DP_OPC[m_base]
        rn = _get_reg(args[0])
        if args[1].startswith('#'):
            return _encode_dp_imm(cond, opc, 1, rn, 0, _parse_imm(args[1]) & 0xFFFFFFFF)
        rm = _get_reg(args[1])
        return _encode_dp_reg(cond, opc, 1, rn, 0, rm)

    # --- MUL ---
    if m_base == 'MUL':
        s = 1 if mnem.endswith('S') else 0
        rd = _get_reg(args[0])
        rm = _get_reg(args[1])
        rs = _get_reg(args[2])
        return _encode_mul(cond, s, rd, rs, rm)

    # --- B / BL ---
    if m_base in ('B', 'BL'):
        link = 1 if m_base == 'BL' else 0
        target_label = args[0].strip()
        if target_label in symbols:
            target = symbols[target_label]
        else:
            try:
                target = _parse_imm(target_label)
            except ValueError:
                target = addr + 8  # fallback: NOP branch
        offset = target - addr
        return _encode_branch(cond, link, offset)

    # --- BX ---
    if m_base == 'BX':
        rm = _get_reg(args[0])
        return _encode_bx(cond, rm)

    # --- LDR (immediate or register) ---
    if m_base == 'LDR' or m_base == 'LDRB':
        b = 1 if m_base == 'LDRB' else 0
        rd = _get_reg(args[0])
        # [rn, #imm] or [rn]
        mem_arg = args[1].strip() if len(args) > 1 else '[r0]'
        m_mem = re.match(r'\[\s*(\w+)\s*(?:,\s*#(-?\d+))?\s*\]', mem_arg)
        if m_mem:
            rn = _get_reg(m_mem.group(1))
            offset = int(m_mem.group(2)) if m_mem.group(2) else 0
            u = 1 if offset >= 0 else 0
            return _encode_ldr_str_imm(cond, 1, u, b, 0, 1, rn, rd, abs(offset))
        # register shifted: [rn, rm, LSL #n]
        m_reg = re.match(r'\[\s*(\w+)\s*,\s*(\w+)(?:\s*,\s*LSL\s*#(\d+))?\s*\]', mem_arg, re.I)
        if m_reg:
            rn = _get_reg(m_reg.group(1))
            rm_r = _get_reg(m_reg.group(2))
            lsl = int(m_reg.group(3)) if m_reg.group(3) else 0
            return (cond << 28) | (0b011 << 25) | (1 << 24) | (1 << 23) | (b << 22) | (1 << 20) | (rn << 16) | (rd << 12) | (lsl << 7) | rm_r
        return None

    # --- STR ---
    if m_base == 'STR':
        rt = _get_reg(args[0])
        mem_arg = args[1].strip() if len(args) > 1 else '[r1]'
        m_mem = re.match(r'\[\s*(\w+)\s*(?:,\s*#(-?\d+))?\s*\]', mem_arg)
        if m_mem:
            rn = _get_reg(m_mem.group(1))
            offset = int(m_mem.group(2)) if m_mem.group(2) else 0
            u = 1 if offset >= 0 else 0
            return _encode_ldr_str_imm(cond, 1, u, 0, 0, 0, rn, rt, abs(offset))
        return None

    # --- PUSH / POP ---
    if m_base == 'PUSH':
        reg_list = _reg_list_bits(args[0])
        return _encode_ldm_stm(cond, 1, 0, 0, 1, 0, 13, reg_list)
    if m_base == 'POP':
        reg_list = _reg_list_bits(args[0])
        return _encode_ldm_stm(cond, 0, 1, 0, 1, 1, 13, reg_list)

    # --- VFP: VLDR.F64 ---
    if mnem.upper() in ('VLDR.F64', 'VLDR'):
        dd = _get_dreg(args[0])
        m_mem = re.match(r'\[\s*(\w+)\s*(?:,\s*#(-?\d+))?\s*\]', args[1])
        rn = _get_reg(m_mem.group(1)) if m_mem else 0
        off = int(m_mem.group(2)) if (m_mem and m_mem.group(2)) else 0
        return _encode_vldr_f64(cond, rn, dd, off)

    # --- VFP: VSTR.F64 ---
    if mnem.upper() in ('VSTR.F64', 'VSTR'):
        dd = _get_dreg(args[0])
        m_mem = re.match(r'\[\s*(\w+)\s*(?:,\s*#(-?\d+))?\s*\]', args[1])
        rn = _get_reg(m_mem.group(1)) if m_mem else 0
        off = int(m_mem.group(2)) if (m_mem and m_mem.group(2)) else 0
        return _encode_vstr_f64(cond, rn, dd, off)

    # --- VFP: VMOV ---
    if mnem.upper() in ('VMOV', 'VMOV.F64'):
        a0 = args[0].strip().lower()
        a1 = args[1].strip().lower() if len(args) > 1 else ''
        a2 = args[2].strip().lower() if len(args) > 2 else ''
        # VMOV.F64 dd, dm
        if mnem.upper() == 'VMOV.F64':
            return _encode_vmov_f64(cond, _get_dreg(a0), _get_dreg(a1))
        # VMOV rt, rt2, dm  (from vfp)
        if a0.startswith('r') and a1.startswith('r') and a2.startswith('d'):
            return _encode_vmov_from_d(cond, _get_reg(a0), _get_reg(a1), _get_dreg(a2))
        # VMOV dm, rt, rt2  (to vfp)
        if a0.startswith('d') and a1.startswith('r') and a2.startswith('r'):
            return _encode_vmov_to_d(cond, _get_reg(a1), _get_reg(a2), _get_dreg(a0))
        # VMOV rt, sn  (arm <- vfp single)
        if a0.startswith('r') and a1.startswith('s'):
            return _encode_vmov_arm_vfp(cond, 1, _get_sreg(a1), _get_reg(a0))
        # VMOV sn, rt  (vfp single <- arm)
        if a0.startswith('s') and a1.startswith('r'):
            return _encode_vmov_arm_vfp(cond, 0, _get_sreg(a0), _get_reg(a1))
        return None

    # --- VFP: VADD / VSUB / VMUL / VDIV ---
    vfp_bin_map = {
        'VADD.F64': 0b001100, 'VSUB.F64': 0b001110,
        'VMUL.F64': 0b001000, 'VDIV.F64': 0b100000,
    }
    if mnem.upper() in vfp_bin_map:
        dd = _get_dreg(args[0])
        dn = _get_dreg(args[1])
        dm = _get_dreg(args[2])
        opc4_map = {'VADD.F64': 3, 'VSUB.F64': 3, 'VMUL.F64': 2, 'VDIV.F64': 8}
        # Using standard ARM VFP encoding
        opc_top = {'VADD.F64': 0xE300B000, 'VSUB.F64': 0xE300B040,
                   'VMUL.F64': 0xE200B000, 'VDIV.F64': 0xE800B000}
        base = opc_top[mnem.upper()]
        d_hi = (dd >> 4) & 1; d_lo = dd & 0xF
        n_hi = (dn >> 4) & 1; n_lo = dn & 0xF
        m_hi = (dm >> 4) & 1; m_lo = dm & 0xF
        return (cond << 28) | (base & 0x0FFFFFFF) | (n_lo << 16) | (d_hi << 22) | (d_lo << 12) | (n_hi << 7) | (m_hi << 5) | m_lo

    # --- VFP: VCVT.S32.F64 ---
    if mnem.upper() == 'VCVT.S32.F64':
        sd = _get_sreg(args[0])
        dm = _get_dreg(args[1])
        return _encode_vcvt_s32_f64(cond, sd, dm)

    # --- VFP: VCVT.F64.S32 ---
    if mnem.upper() == 'VCVT.F64.S32':
        dd = _get_dreg(args[0])
        sm = _get_sreg(args[1])
        return _encode_vcvt_f64_s32(cond, dd, sm)

    # --- VFP: VCMP.F64 ---
    if mnem.upper() == 'VCMP.F64':
        dd = _get_dreg(args[0])
        dm = _get_dreg(args[1])
        return _encode_vcmp_f64(cond, dd, dm)

    # --- VFP: VMRS ---
    if mnem.upper() == 'VMRS':
        return _encode_vmrs(cond)

    # Instrução não reconhecida: emite NOP (MOV r0, r0)
    return _encode_dp_reg(0xE, 0xD, 0, 0, 0, 0)


def _encode_ldr_pseudo(instr: _Instr, symbols: dict[str, int]) -> int:
    """Codifica LDR rX, =label_ou_imm como LDR rX, [PC, #offset]."""
    rd = _get_reg(instr.ldr_reg)
    pool_label = instr.pool_entry
    if pool_label not in symbols:
        return _encode_dp_reg(0xE, 0xD, 0, 0, rd, rd)  # NOP
    pool_addr = symbols[pool_label]
    # PC durante execução = addr + 8 (pipeline de 3 estágios)
    offset = pool_addr - (instr.address + 8)
    u = 1 if offset >= 0 else 0
    abs_off = abs(offset)
    if abs_off > 0xFFF:
        abs_off = 0  # fallback
    return _encode_ldr_str_imm(0xE, 1, u, 0, 0, 1, 15, rd, abs_off)


# ---------------------------------------------------------------------------
# Geração do segmento .data
# ---------------------------------------------------------------------------

def _encode_data_section(instrucoes: list[_Instr], symbols: dict[str, int]) -> bytes:
    """Codifica labels e valores do segmento .data em bytes."""
    data_bytes = bytearray()
    in_data = False
    for instr in instrucoes:
        if instr.is_directive:
            if instr.directive == '.data':
                in_data = True
                continue
            if not in_data:
                continue
            if instr.directive == '.double':
                try:
                    val = float(instr.directive_args.strip())
                except ValueError:
                    val = 0.0
                data_bytes += struct.pack('<d', val)
            elif instr.directive == '.word':
                val_str = instr.directive_args.strip()
                if val_str in symbols:
                    val = symbols[val_str]
                else:
                    try:
                        val = _parse_imm(val_str)
                    except (ValueError, OverflowError):
                        val = 0
                data_bytes += struct.pack('<I', val & 0xFFFFFFFF)
            elif instr.directive == '.byte':
                for b_str in instr.directive_args.split(','):
                    try:
                        data_bytes += struct.pack('B', _parse_imm(b_str.strip()) & 0xFF)
                    except Exception:
                        data_bytes += b'\x00'
            elif instr.directive == '.space':
                try:
                    n = _parse_imm(instr.directive_args.split(',')[0].strip())
                except (ValueError, IndexError):
                    n = 0
                data_bytes += b'\x00' * n
            elif instr.directive == '.balign':
                try:
                    n = _parse_imm(instr.directive_args.strip())
                    if n > 0 and len(data_bytes) % n != 0:
                        data_bytes += b'\x00' * (n - (len(data_bytes) % n))
                except ValueError:
                    pass
    return bytes(data_bytes)


# ---------------------------------------------------------------------------
# Codificação de texto → bytes (passo 2 completo)
# ---------------------------------------------------------------------------

def _pass2(instrucoes: list[_Instr], symbols: dict[str, int]) -> tuple[bytes, bytes, int]:
    """Retorna (text_bytes, data_bytes, data_start_addr)."""
    text_words = []
    data_start = BASE_TEXT

    for instr in instrucoes:
        if instr.is_directive:
            if instr.directive == '.data':
                data_start = instr.address if hasattr(instr, 'address') else BASE_TEXT
            continue
        if not instr.mnemonic:
            continue
        word = _encode_instr(instr, symbols)
        if word is not None:
            text_words.append(struct.pack('<I', word & 0xFFFFFFFF))

    text_bytes = b''.join(text_words)
    data_bytes = _encode_data_section(instrucoes, symbols)
    return text_bytes, data_bytes, data_start


# ---------------------------------------------------------------------------
# Geração Intel HEX
# ---------------------------------------------------------------------------

def _ihex_record(rec_type: int, address: int, data: bytes) -> str:
    count = len(data)
    addr_hi = (address >> 8) & 0xFF
    addr_lo = address & 0xFF
    body = bytes([count, addr_hi, addr_lo, rec_type]) + data
    checksum = (-sum(body)) & 0xFF
    return ':' + body.hex().upper() + f'{checksum:02X}'


def _bytes_to_ihex(data: bytes, base_addr: int = 0) -> list[str]:
    records = []
    CHUNK = 16
    for offset in range(0, len(data), CHUNK):
        chunk = data[offset:offset + CHUNK]
        addr = (base_addr + offset) & 0xFFFF
        # Segmento estendido (tipo 02) se necessário
        if base_addr + offset > 0xFFFF:
            ext = (base_addr + offset) >> 16
            records.append(_ihex_record(2, 0, bytes([ext >> 8, ext & 0xFF])))
        records.append(_ihex_record(0, addr, chunk))
    return records


def gerar_hex(asm_texto: str) -> str:
    """Converte texto assembly ARMv7 em string no formato Intel HEX."""
    instrucoes, symbols = _pass1(asm_texto)
    # Reatribui endereços após inserção dos pools
    _reassign_addresses(instrucoes, symbols)
    text_bytes, data_bytes, data_start = _pass2(instrucoes, symbols)

    records = []
    records.extend(_bytes_to_ihex(text_bytes, BASE_TEXT))
    if data_bytes:
        records.extend(_bytes_to_ihex(data_bytes, data_start))
    records.append(':00000001FF')  # EOF
    return '\n'.join(records) + '\n'


def gerar_words_cpulator(asm_texto: str) -> str:
    """Gera um .s contendo só o código de máquina em hexadecimal (.word).

    O CPUlator (ARMv7 DE1-SoC) não importa arquivos Intel HEX, mas o seu
    montador embutido aceita ``.word 0x...``. Cada palavra é exatamente o
    opcode de 32 bits que o linker produziu — ou seja, este arquivo É o
    hexadecimal, num formato que se cola no editor e roda com
    "Compile and Load". Como o programa de Morse é independente de posição
    (endereços de periférico via MOVW/MOVT e desvios PC-relativos), roda em
    qualquer endereço de carga.
    """
    instrucoes, symbols = _pass1(asm_texto)
    _reassign_addresses(instrucoes, symbols)
    text_bytes, data_bytes, _ = _pass2(instrucoes, symbols)

    linhas = [
        "@ ===================================================================",
        "@  RA4 — CODIGO DE MAQUINA (HEXADECIMAL) gerado pelo linker proprio.",
        "@  Como usar no CPUlator (https://cpulator.01xz.net, ARMv7 DE1-SoC):",
        "@    1) selecione todo este texto e cole no editor (apague o exemplo);",
        "@    2) clique em 'Compile and Load' (F5);",
        "@    3) clique em 'Continue' (F3) e observe o LED0 (painel LEDR).",
        "@  Cada .word abaixo é uma instrucao ARM de 32 bits (little-endian).",
        "@ ===================================================================",
        ".global _start",
        ".text",
        "_start:",
    ]
    for i in range(0, len(text_bytes), 4):
        w = struct.unpack('<I', text_bytes[i:i + 4])[0]
        linhas.append(f"    .word 0x{w:08X}")
    if data_bytes:
        linhas.append("@ ---- dados ----")
        for i in range(0, len(data_bytes), 4):
            chunk = data_bytes[i:i + 4].ljust(4, b'\x00')
            w = struct.unpack('<I', chunk)[0]
            linhas.append(f"    .word 0x{w:08X}")
    return "\n".join(linhas) + "\n"


def _reassign_addresses(instrucoes: list[_Instr], symbols: dict[str, int]) -> None:
    """Recalcula endereços depois de inseridos os pools."""
    addr = BASE_TEXT
    data_section = False
    for instr in instrucoes:
        if instr.is_directive:
            if instr.directive == '.text':
                data_section = False
            elif instr.directive == '.data':
                if addr % 8 != 0:
                    addr += 8 - (addr % 8)
                data_section = True
            elif instr.directive == '.double':
                if instr.label:
                    symbols[instr.label] = addr
                addr += 8
            elif instr.directive == '.word':
                if instr.label:
                    symbols[instr.label] = addr
                addr += 4
            elif instr.directive == '.byte':
                if instr.label:
                    symbols[instr.label] = addr
                count = len(instr.directive_args.split(','))
                addr += count
            elif instr.directive == '.space':
                if instr.label:
                    symbols[instr.label] = addr
                try:
                    addr += _parse_imm(instr.directive_args.split(',')[0].strip())
                except (ValueError, IndexError):
                    pass
            elif instr.directive == '.balign':
                try:
                    n = _parse_imm(instr.directive_args.strip())
                    if n > 0 and addr % n != 0:
                        addr += n - (addr % n)
                except ValueError:
                    pass
                if instr.label:
                    symbols[instr.label] = addr
        else:
            instr.address = addr
            if instr.label:
                symbols[instr.label] = addr
            if instr.mnemonic:
                addr += 4
