/* Entry stubs for the pad hooks, both in the game's per-frame pad loop.  Every volatile
 * register is free at both sites; the loop keeps its state in r17-r31:
 *   r17 = the input manager (+4: the per-channel records, 0x38 bytes each)   r26 = channel * 0x38
 *   r21 = &this channel's KPAD status buffer pointer    r18 = statuses KPADRead returned
 *   r22 = this channel's PADStatus (PADRead + PADClamp) r20 = channel
 *
 * Each hook keeps a little state inside its own body (zero when installed), so it needs no
 * free RAM of the game's: the same words work as a patched DOL, a Riivolution patch or a
 * Gecko C2 code.  The last word is the slot the installer turns into the branch back. */
    .section .padstart, "ax"
    b       _entry

    .section .padtail, "ax"
    .globl _entry
_entry:
#if defined(HOOK_REMOTE)
    # remote mode, just before the converter (lwz r0,4(r17))
    stwu    1, -0x20(1)
    mflr    0
    stw     0, 0x24(1)
    lwz     3, 0(21)            # KPAD statuses
    mr      4, 18               # how many
    mr      5, 22               # PADStatus
    mr      6, 20               # channel
    bl      1f                  # r7 = the state below
    .space  0x40
1:  mflr    7
    bl      pad_remote
    lwz     0, 0x24(1)
    mtlr    0
    addi    1, 1, 0x20
    lwz     0, 4(17)            # original instruction
#elif defined(HOOK_PAD)
    # pad mode: replaces "bl <pad converter>" (r3 = the record, r4 = PADStatus)
    stwu    1, -0x20(1)
    mflr    0
    stw     0, 0x24(1)
    bl      pad_converter       # the original call (address given to the linker)
    lwz     3, 4(17)
    add     3, 3, 26            # the record
    mr      4, 22               # PADStatus
    mr      5, 20               # channel
    lwz     7, 0(21)            # KPAD status buffer
    bl      1f                  # r6 = the state below
    .space  0x40
1:  mflr    6
    bl      pad_only
    lwz     0, 0x24(1)
    mtlr    0
    addi    1, 1, 0x20
#endif
    nop
