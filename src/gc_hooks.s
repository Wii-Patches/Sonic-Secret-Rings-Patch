# Sonic and the Secret Rings - GameCube Controller Hook Trampoline
# Assembled into GC_BASE (0x80002000)
#
# Reads GameCube Controller plugged into Port 1 directly via Serial Interface
# hardware registers (0xCD006404).

.globl gc_button_hook
gc_button_hook:
    # 1. Check GameCube Controller from hardware Serial Interface (channel 0)
    lis     r6, 0xCD00
    lwz     r8, 0x6404(r6)              # SIC0INBUFH
    cmpwi   r8, 0
    blt     gc_btn_done                 # error / no response
    andis.  r6, r8, 0x0080
    beq     gc_btn_done                 # bit 23 not set -> not a valid pad
    srwi    r9, r8, 16                  # r9 = GameCube button word

    # Map GameCube Buttons:
    # GC A -> Wiimote 2 (Jump / Accelerate)
    andi.   r6, r9, 0x0100
    beq     gc_b
    ori     r0, r0, 0x0100

gc_b:
    # GC B -> Wiimote 1 (Brake / Back)
    andi.   r6, r9, 0x0200
    beq     gc_x
    ori     r0, r0, 0x0200

gc_x:
    # GC X -> Wiimote A (Speed Break)
    andi.   r6, r9, 0x0400
    beq     gc_y
    ori     r0, r0, 0x0800

gc_y:
    # GC Y -> Wiimote B (Time Break)
    andi.   r6, r9, 0x0800
    beq     gc_start
    ori     r0, r0, 0x0400

gc_start:
    # GC Start -> Plus (Pause)
    andi.   r6, r9, 0x1000
    beq     gc_z
    ori     r0, r0, 0x0010

gc_z:
    # GC Z -> Minus
    andi.   r6, r9, 0x0010
    beq     gc_l
    ori     r0, r0, 0x1000

gc_l:
    # GC L -> Wiimote D-Up (Step Left)
    andi.   r6, r9, 0x0040
    beq     gc_r
    ori     r0, r0, 0x0008

gc_r:
    # GC R -> Wiimote D-Down (Step Right)
    andi.   r6, r9, 0x0020
    beq     gc_dup
    ori     r0, r0, 0x0004

gc_dup:
    # GC Up -> Sideways Wiimote Right
    andi.   r6, r9, 0x0008
    beq     gc_ddown
    ori     r0, r0, 0x0002

gc_ddown:
    # GC Down -> Sideways Wiimote Left
    andi.   r6, r9, 0x0004
    beq     gc_dleft
    ori     r0, r0, 0x0001

gc_dleft:
    # GC Left -> Sideways Wiimote Up
    andi.   r6, r9, 0x0001
    beq     gc_dright
    ori     r0, r0, 0x0008

gc_dright:
    # GC Right -> Sideways Wiimote Down
    andi.   r6, r9, 0x0002
    beq     gc_btn_done
    ori     r0, r0, 0x0004

gc_btn_done:
    stw     r0, 0(r3)                   # Store updated Wiimote button mask
    mr      r5, r0                      # Return updated button word in r5/r0
    blr

# GameCube Controller Tilt & Steering Hook
# Site: cmplwi r30, 1
.globl gc_tilt_hook
gc_tilt_hook:
    stwu    sp, -0x20(sp)
    mflr    r0
    stw     r0, 0x24(sp)

    # Check if GameCube Controller is answering on SI channel 0
    lis     r5, 0xCD00
    lwz     r6, 0x6404(r5)              # SIC0INBUFH
    cmpwi   r6, 0
    blt     gc_tilt_exit
    andis.  r7, r6, 0x0080
    beq     gc_tilt_exit

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

    # Scale factor for GC stick: 1.0 / 80.0 ~= 0.0125
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

gc_tilt_exit:
    lwz     r0, 0x24(sp)
    mtlr    r0
    addi    sp, sp, 0x20
    cmplwi  r30, 1                      # Displaced instruction
    blr

# GameCube Hardware SI Poller Hook
# Hooked into KPADRead setup to ensure SI auto-polling is running
.globl gc_poller_hook
gc_poller_hook:
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
