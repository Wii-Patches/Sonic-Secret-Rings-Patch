# Sonic and the Secret Rings - Classic Controller Hook Trampoline
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

.globl cc_button_hook
cc_button_hook:
    # 1. Displaced logic: Read Classic Controller bitfield if plugged in
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
    beq     cc_done
    ori     r0, r0, 0x1000              # Classic Minus -> Minus

cc_done:
    stw     r0, 0(r3)                   # Store updated Wiimote button mask
    mr      r5, r0                      # Return updated button word in r5/r0
    blr

# Classic Controller Tilt Hook
# Site: cmplwi r30, 1 (tilt filtering function)
# r30 holds extension type: 0=none, 1=nunchuk, 2=classic
# r28 points to player filtered motion struct
.globl cc_tilt_hook
cc_tilt_hook:
    stwu    sp, -0x20(sp)
    mflr    r0
    stw     r0, 0x24(sp)

    cmplwi  r30, 2                      # Is Classic Controller plugged in?
    bne     cc_tilt_exit

    # Classic Controller left stick at KPAD struct channel 0
    # Left stick X is float at +0x6C, Y is float at +0x70
    lis     r5, 0x8069
    lfs     f0, 0x2BCC(r5)              # Stick X (-1.0 .. 1.0)
    lfs     f1, 0x2BD0(r5)              # Stick Y (-1.0 .. 1.0)

    # Scale steering: 0.85
    lis     r6, 0x3F5A
    stw     r6, 0x08(sp)
    lfs     f2, 0x08(sp)
    fmuls   f0, f0, f2

    # Scale pitch: 0.75
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

cc_tilt_exit:
    lwz     r0, 0x24(sp)
    mtlr    r0
    addi    sp, sp, 0x20
    cmplwi  r30, 1                      # Displaced instruction
    blr
