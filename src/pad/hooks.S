/* Entry stub for the pad hook.
 *
 * Site: the game's per-frame pad loop, in the remote-mode branch, just before it hands this
 * channel's KPAD statuses to its converter (lwz r0,4(r17)).  Every volatile register is free
 * there; the loop keeps its state in r17-r31:
 *   r21 = &this channel's KPAD status buffer pointer      r18 = statuses KPADRead returned
 *   r22 = this channel's PADStatus (PADRead + PADClamp)   r20 = channel
 *
 * The hook keeps a little state inside its own body (zero when installed), so it needs no
 * free RAM of the game's: the same words work as a patched DOL, a Riivolution patch or a
 * Gecko C2 code.  The last word is the slot the installer turns into the branch back. */
    .section .padstart, "ax"
    b       _entry

    .section .padtail, "ax"
    .globl _entry
_entry:
    stwu    1, -0x20(1)
    mflr    0
    stw     0, 0x24(1)
    lwz     3, 0(21)            # KPAD statuses
    mr      4, 18               # how many
    mr      5, 22               # PADStatus
    mr      6, 20               # channel
    bl      1f                  # r7 = the scratch words below
    .space  0x40
1:  mflr    7
    bl      pad_merge
    lwz     0, 0x24(1)
    mtlr    0
    addi    1, 1, 0x20
    lwz     0, 4(17)            # original instruction
    nop
