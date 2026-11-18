/* Entry stubs for the pad hooks.  The pad loop keeps its state in r17-r31 and every volatile
 * register is free at both of its sites:
 *   r21 = &this channel's KPAD status buffer pointer    r18 = statuses KPADRead returned
 *   r22 = this channel's PADStatus (PADRead + PADClamp) r20 = channel
 *   r24 = &this channel's "remote connected" byte   r26 = channel * 0x38 (records at 4(r17))
 *
 * The shared state (pad_state, zero when installed) sits in the first hook's body, so no free
 * RAM of the game's is needed.  The last word of each stub is the slot the installer turns into
 * the branch back. */
    .section .padstart, "ax"
    b       _entry
#if defined(HOOK_REMOTE)
    .globl  pad_state
pad_state:
    .space  0x60
#endif

    .section .padtail, "ax"
    .globl _entry
_entry:
#if defined(HOOK_REMOTE)
    # pad loop, just before the remote-mode converter (lwz r0,4(r17))
    stwu    1, -0x20(1)
    mflr    0
    stw     0, 0x24(1)
    lwz     3, 0(21)            # KPAD statuses
    mr      4, 18               # how many
    mr      5, 20               # channel
    lis     6, pad_state@ha
    addi    6, 6, pad_state@l
    bl      pad_remote
    mr      18, 3               # a status made up for a pad with no remote
    lwz     0, 0x24(1)
    mtlr    0
    addi    1, 1, 0x20
    lwz     0, 4(17)            # original instruction
    nop
#elif defined(HOOK_TOP)
    # pad loop, top of each channel (lwz r0,4(r17))
    stwu    1, -0x20(1)
    mflr    0
    stw     0, 0x24(1)
    mr      3, 22               # PADStatus
    mr      4, 20               # channel
    mr      5, 24               # this channel's "remote connected" byte
    lwz     6, 0(21)            # KPAD status buffer
    lwz     7, 4(17)
    add     7, 7, 26            # this channel's record
    bl      pad_top
    lwz     0, 0x24(1)
    mtlr    0
    addi    1, 1, 0x20
    cmpwi   3, 0
    beq     1f
    lis     12, loop_next@ha    # handled: on to the next channel
    addi    12, 12, loop_next@l
    mtctr   12
    bctr
1:  lwz     0, 4(17)            # original instruction
    nop
#endif
