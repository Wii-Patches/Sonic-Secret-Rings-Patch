# Combined GameCube & Classic Controller Patch for Sonic and the Secret Rings
# Assembled into CAVE_BASE (0x80001820)
#
# Register state at button site:
#   r0: Wiimote buttons read from KPAD
#   r4: pointer to KPAD status / extension buffer
#   r3: pointer to destination buffer (0x60 is raw buttons, 0x0 is final buttons)
#
# Classic Controller bitfield is at 42(r4).
# Displaced instruction:
#   lhz     r0, 42(r4)
#   stw     r0, 96(r3)

.globl hook_buttons
hook_buttons:
    # 1. Displaced logic: Read Classic Controller bitfield if present
    lhz     r0, 42(r4)                  # Classic bitfield
    stw     r0, 96(r3)                  # Store raw classic buttons at 0x60(r3)
    mr      r5, r0                      # r5 = Classic bitfield

    # Check Classic Home
    andi.   r6, r5, 0x0800
    beq     cc_up
    ori     r0, r0, 0x8000              # Home -> Home

cc_up:
    andi.   r6, r5, 0x0001
    beq     cc_down
    ori     r0, r0, 0x0002              # D-Up -> Right (sideways Wiimote)

cc_down:
    andi.   r6, r5, 0x4000
    beq     cc_left
    ori     r0, r0, 0x0001              # D-Down -> Left (sideways Wiimote)

cc_left:
    andi.   r6, r5, 0x0002
    beq     cc_right
    ori     r0, r0, 0x0008              # D-Left -> Up (sideways Wiimote)

cc_right:
    andi.   r6, r5, 0x8000
    beq     cc_a
    ori     r0, r0, 0x0004              # D-Right -> Down (sideways Wiimote)

cc_a:
    andi.   r6, r5, 0x0010
    beq     cc_b
    ori     r0, r0, 0x0100              # Classic A -> Button 2 (Jump / Accelerate)

cc_b:
    andi.   r6, r5, 0x0040
    beq     cc_x
    ori     r0, r0, 0x0200              # Classic B -> Button 1 (Brake / Back)

cc_x:
    andi.   r6, r5, 0x0008
    beq     cc_y
    ori     r0, r0, 0x0800              # Classic X -> Button A (Action / Speed Break)

cc_y:
    andi.   r6, r5, 0x0020
    beq     cc_l
    ori     r0, r0, 0x0400              # Classic Y -> Button B (Time Break)

cc_l:
    andi.   r6, r5, 0x2000
    beq     cc_r
    ori     r0, r0, 0x0008              # Classic L -> Wiimote D-Up (Step Left)

cc_r:
    andi.   r6, r5, 0x0200
    beq     cc_zl
    ori     r0, r0, 0x0004              # Classic R -> Wiimote D-Down (Step Right)

cc_zl:
    andi.   r6, r5, 0x0080
    beq     cc_zr
    ori     r0, r0, 0x0008              # Classic ZL -> Step Left

cc_zr:
    andi.   r6, r5, 0x0004
    beq     cc_plus
    ori     r0, r0, 0x0004              # Classic ZR -> Step Right

cc_plus:
    andi.   r6, r5, 0x0400
    beq     cc_minus
    ori     r0, r0, 0x0010              # Classic Plus -> Plus (Pause)

cc_minus:
    andi.   r6, r5, 0x1000
    beq     gc_check
    ori     r0, r0, 0x1000              # Classic Minus -> Minus

gc_check:
    # 2. Check GameCube Controller from hardware Serial Interface (channel 0)
    lis     r6, 0xCD00
    lwz     r8, 0x6404(r6)              # SIC0INBUFH
    cmpwi   r8, 0
    blt     btn_finish                  # error / no response
    andis.  r6, r8, 0x0080
    beq     btn_finish                  # bit 23 not set -> not a valid pad
    srwi    r9, r8, 16                  # r9 = GameCube button word

    # Map GameCube Buttons:
    andi.   r6, r9, 0x0100              # GC A -> Wiimote 2
    beq     gc_b
    ori     r0, r0, 0x0100

gc_b:
    andi.   r6, r9, 0x0200              # GC B -> Wiimote 1
    beq     gc_x
    ori     r0, r0, 0x0200

gc_x:
    andi.   r6, r9, 0x0400              # GC X -> Wiimote A (Speed Break)
    beq     gc_y
    ori     r0, r0, 0x0800

gc_y:
    andi.   r6, r9, 0x0800              # GC Y -> Wiimote B (Time Break)
    beq     gc_start
    ori     r0, r0, 0x0400

gc_start:
    andi.   r6, r9, 0x1000              # GC Start -> Plus
    beq     gc_z
    ori     r0, r0, 0x0010

gc_z:
    andi.   r6, r9, 0x0010              # GC Z -> Minus
    beq     gc_l
    ori     r0, r0, 0x1000

gc_l:
    andi.   r6, r9, 0x0040              # GC L -> Step Left
    beq     gc_r
    ori     r0, r0, 0x0008

gc_r:
    andi.   r6, r9, 0x0020              # GC R -> Step Right
    beq     gc_dup
    ori     r0, r0, 0x0004

gc_dup:
    andi.   r6, r9, 0x0008              # GC Up -> Sideways Right
    beq     gc_ddown
    ori     r0, r0, 0x0002

gc_ddown:
    andi.   r6, r9, 0x0004              # GC Down -> Sideways Left
    beq     gc_dleft
    ori     r0, r0, 0x0001

gc_dleft:
    andi.   r6, r9, 0x0001              # GC Left -> Sideways Up
    beq     gc_dright
    ori     r0, r0, 0x0008

gc_dright:
    andi.   r6, r9, 0x0002              # GC Right -> Sideways Down
    beq     btn_finish
    ori     r0, r0, 0x0004

btn_finish:
    stw     r0, 0(r3)                   # Store updated Wiimote button mask
    mr      r5, r0                      # Return updated button word in r5/r0
    blr

.globl hook_tilt
hook_tilt:
    # Preserve stack frame:
    stwu    sp, -0x20(sp)
    mflr    r0
    stw     r0, 0x24(sp)

    # Check if Classic Controller is connected (r30 == 2)
    cmplwi  r30, 2
    beq     read_classic_stick

    # Check if GameCube Controller is answering on SI channel 0
    lis     r5, 0xCD00
    lwz     r6, 0x6404(r5)              # SIC0INBUFH
    cmpwi   r6, 0
    blt     tilt_done
    andis.  r7, r6, 0x0080
    beq     tilt_done

    # Extract GameCube Control Stick X & Y
    rlwinm  r7, r6, 24, 24, 31          # GC Stick X (0..255, center 128)
    addi    r7, r7, -128                # -128..127
    rlwinm  r8, r6, 0, 24, 31           # GC Stick Y (0..255, center 128)
    addi    r8, r8, -128

    # Deadzone check (deadzone = 12)
    srawi   r9, r7, 31
    xor     r10, r7, r9
    subf    r10, r9, r10                # abs(X)
    cmpwi   r10, 12
    bge     gc_x_ok
    li      r7, 0
gc_x_ok:
    srawi   r9, r8, 31
    xor     r10, r8, r9
    subf    r10, r9, r10                # abs(Y)
    cmpwi   r10, 12
    bge     gc_y_ok
    li      r8, 0
gc_y_ok:

    # Float conversion:
    lis     r0, 0x4330
    stw     r0, 0x08(sp)
    xoris   r7, r7, 0x8000
    stw     r7, 0x0C(sp)
    lfd     f0, 0x08(sp)
    lis     r0, 0x8000
    stw     r0, 0x10(sp)
    stw     r0, 0x14(sp)
    lfd     f2, 0x10(sp)
    fsub    f0, f0, f2                 # f0 = float(stickX)

    # Scale factor for GC stick -> tilt: 1.0 / 80.0 ~= 0.0125
    lis     r0, 0x3C4D
    ori     r0, r0, 0x0000
    stw     r0, 0x0C(sp)
    lfs     f2, 0x0C(sp)
    fmuls   f0, f0, f2                 # f0 = normalized steering [-1.0, 1.0]

    # Convert Y:
    lis     r0, 0x4330
    stw     r0, 0x08(sp)
    xoris   r8, r8, 0x8000
    stw     r8, 0x0C(sp)
    lfd     f1, 0x08(sp)
    fsub    f1, f1, f2                 # f1 = float(stickY)
    fmuls   f1, f1, f2                 # f1 = normalized pitch [-1.0, 1.0]

    b       apply_tilt

read_classic_stick:
    # Classic Controller stick at channel 0 KPAD struct (0x80692B60)
    # Left stick X is at +0x6C, Y is at +0x70
    lis     r5, 0x8069
    lfs     f0, 0x2BCC(r5)              # Stick X (-1.0 .. 1.0)
    lfs     f1, 0x2BD0(r5)              # Stick Y (-1.0 .. 1.0)

apply_tilt:
    # Scale steering: 0.85
    # Scale pitch: 0.75
    lis     r6, 0x3F5A
    stw     r6, 0x08(sp)
    lfs     f2, 0x08(sp)
    fmuls   f0, f0, f2

    lis     r7, 0x3F40
    stw     r7, 0x0C(sp)
    lfs     f3, 0x0C(sp)
    fmuls   f1, f1, f3

    # Invert to match Wiimote sideways tilt direction
    fneg    f0, f0
    fneg    f1, f1

    # Store into filtered accelerometer values in player struct r28:
    stfs    f0, 0x0008(r28)
    stfs    f0, 0x0014(r28)
    stfs    f0, 0x0068(r28)
    stfs    f1, 0x0010(r28)
    stfs    f1, 0x006C(r28)

tilt_done:
    lwz     r0, 0x24(sp)
    mtlr    r0
    addi    sp, sp, 0x20
    cmplwi  r30, 1                      # Displaced instruction: check Nunchuk
    blr

.globl hook_poller
hook_poller:
    # Displaced instructions from poll hook site:
    lwz     r9, 12(r3)
    lwz     r8, 16(r3)

    # Enable SI hardware auto-polling:
    lis     r6, 0xCD00
    lis     r7, 0x0040
    ori     r7, r7, 0x0300
    stw     r7, 0x6400(r6)              # SIC0OUTBUF: poll command (0x00400300)

    # Ack latched status & trigger WR
    lis     r7, 0x8F0F
    ori     r7, r7, 0x0F0F
    stw     r7, 0x6438(r6)              # SISR

    # Set SIPOLL enable channel 0
    lwz     r7, 0x6430(r6)              # SIPOLL
    rlwinm  r7, r7, 0, 0, 23            # clear enable byte
    ori     r7, r7, 0x0188              # Y=1, Channel 0 EN + VBCPY
    stw     r7, 0x6430(r6)              # SIPOLL

    blr
