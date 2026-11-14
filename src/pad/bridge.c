/* GameCube controller (port 1-4) and Classic Controller support for Sonic and the Secret Rings.
 *
 * The game already reads the GameCube pads itself (PADRead, every frame) and has an input
 * path for them, but it only uses that path for a channel that has no Wii Remote; with a Wii
 * Remote connected -- always the case on a console -- the pad is ignored, and so is a Classic
 * Controller on the remote.  Story mode steers by tilting the sideways remote.
 *
 * One hook in the game's per-frame pad loop runs just before a channel's KPAD statuses are
 * turned into the game's input record (remote mode only).  While a GameCube pad (the port
 * matching the channel) or a Classic Controller (on that remote) is in use, it rewrites those
 * statuses so they look like the remote doing the same thing:
 *
 *   - the pad's buttons are ORed into the remote's button word as the remote buttons they
 *     stand for (the remote's own buttons keep working), and
 *   - the accelerometer reads as the remote tilted by the pad's left stick: left / right
 *     steers, forward / back leans.  The game then runs it through its own calibration and
 *     smoothing exactly as it does for a real remote.
 *
 * The remote's own tilt is replaced while a pad is in use, so a remote lying on the table
 * does not steer.  Built once per variant (USE_GC / USE_CC) by tools/build.py.
 */
typedef unsigned int u32;
typedef signed int s32;
typedef unsigned short u16;
typedef signed char s8;
typedef unsigned char u8;

/* Wii Remote buttons as KPAD reports them */
#define WM_LEFT  0x0001
#define WM_RIGHT 0x0002
#define WM_DOWN  0x0004
#define WM_UP    0x0008
#define WM_PLUS  0x0010
#define WM_2     0x0100     /* jump / accelerate / confirm */
#define WM_1     0x0200     /* brake / back */
#define WM_B     0x0400
#define WM_A     0x0800
#define WM_MINUS 0x1000
#define WM_HOME  0x8000

/* PADStatus.button */
#define PAD_LEFT  0x0001
#define PAD_RIGHT 0x0002
#define PAD_DOWN  0x0004
#define PAD_UP    0x0008
#define PAD_Z     0x0010
#define PAD_R     0x0020
#define PAD_L     0x0040
#define PAD_A     0x0100
#define PAD_B     0x0200
#define PAD_X     0x0400
#define PAD_Y     0x0800
#define PAD_START 0x1000

/* Classic Controller buttons as KPAD reports them */
#define CL_UP    0x0001
#define CL_LEFT  0x0002
#define CL_ZR    0x0004
#define CL_X     0x0008
#define CL_A     0x0010
#define CL_Y     0x0020
#define CL_B     0x0040
#define CL_ZL    0x0080
#define CL_R     0x0200
#define CL_PLUS  0x0400
#define CL_HOME  0x0800
#define CL_MINUS 0x1000
#define CL_L     0x2000
#define CL_DOWN  0x4000
#define CL_RIGHT 0x8000

/* KPADStatus (this SDK) */
#define KPAD_SIZE 0x88
#define K_HOLD    0x00
#define K_ACC     0x0C      /* x, y, z in g; held sideways and flat: (0, -1, 0) */
#define K_DEV     0x5C      /* u32: 0 remote, 1 Nunchuk, 2 Classic Controller */
#define K_CLHOLD  0x60
#define K_ERR     0x85

/* per channel: the last PADStatus that arrived without an error.  The game polls its pads
 * more often than the Serial Interface delivers a new response, so in a stage most frames
 * read PAD_ERR_TRANSFER ("nothing new yet"); the pad is still there, with the last state. */
struct cache {
    u8 pad[12];
    u32 valid;
};

static inline float clamp1(float v)
{
    return v > 1.0f ? 1.0f : v < -1.0f ? -1.0f : v;
}

/* a stick axis, -1..1, with the dead zone removed */
static inline float dz(float v)
{
    const float d = 0.12f;
    if (v > d)
        return clamp1((v - d) / (1.0f - d));
    if (v < -d)
        return clamp1((v + d) / (1.0f - d));
    return 0.0f;
}

/* square root without fsqrt (Broadway has none): rsqrte estimate + Newton steps */
static float sqrtf_(float x)
{
    double y;
    int i;
    if (x <= 0.0f)
        return 0.0f;
    __asm__("frsqrte %0,%1" : "=f"(y) : "f"((double)x));
    for (i = 0; i < 3; i++)
        y = y * (1.5 - 0.5 * x * y * y);
    return (float)(x * y);
}

#ifdef USE_GC
static u32 gc_buttons(u32 b)
{
    u32 o = 0;
    if (b & PAD_A) o |= WM_2;
    if (b & PAD_B) o |= WM_1;
    if (b & PAD_X) o |= WM_A;
    if (b & PAD_Y) o |= WM_B;
    if (b & PAD_L) o |= WM_UP;          /* step left */
    if (b & PAD_R) o |= WM_DOWN;        /* step right */
    if (b & PAD_START) o |= WM_PLUS;
    if (b & PAD_Z) o |= WM_MINUS;
    /* the D-pad as it sits on a sideways remote */
    if (b & PAD_UP) o |= WM_RIGHT;
    if (b & PAD_DOWN) o |= WM_LEFT;
    if (b & PAD_LEFT) o |= WM_UP;
    if (b & PAD_RIGHT) o |= WM_DOWN;
    return o;
}
#endif

#ifdef USE_CC
static u32 cc_buttons(u32 b)
{
    u32 o = 0;
    if (b & CL_A) o |= WM_2;
    if (b & CL_B) o |= WM_1;
    if (b & CL_X) o |= WM_A;
    if (b & CL_Y) o |= WM_B;
    if (b & (CL_L | CL_ZL)) o |= WM_UP;
    if (b & (CL_R | CL_ZR)) o |= WM_DOWN;
    if (b & CL_PLUS) o |= WM_PLUS;
    if (b & CL_MINUS) o |= WM_MINUS;
    if (b & CL_HOME) o |= WM_HOME;
    if (b & CL_UP) o |= WM_RIGHT;
    if (b & CL_DOWN) o |= WM_LEFT;
    if (b & CL_LEFT) o |= WM_UP;
    if (b & CL_RIGHT) o |= WM_DOWN;
    return o;
}
#endif

/* k: this channel's KPAD statuses (k[0] the newest), n of them; pad: its PADStatus */
void pad_merge(u8 *k, s32 n, u8 *pad, u32 chan, struct cache *c)
{
    u32 add = 0;
    int used = 0;
    float sx = 0, sy = 0, ax, az, ay;
    s32 i;

#ifdef DEBUG_ADDR
    {
        volatile u32 *dbg = (volatile u32 *)DEBUG_ADDR;
        dbg[0]++;
        dbg[1] = (u32)n;
        dbg[2] = chan;
        dbg[3] = ((u32)pad[10] << 24) | *(u16 *)pad;
        dbg[4] = (u32)k;
    }
#endif
    (void)pad;
    (void)c;
    (void)chan;

#ifdef USE_GC
    /* keep the pad's last good response up to date even on frames without remote statuses */
    if (chan < 4) {
        s8 err = (s8)pad[10];
        c += chan;
        if (err == 0) {                     /* PAD_ERR_NONE: a fresh response */
            for (i = 0; i < 12; i++)
                c->pad[i] = pad[i];
            c->valid = 1;
        } else if (err != -3) {             /* anything but PAD_ERR_TRANSFER: no pad */
            c->valid = 0;
        }
    }
#endif
    if (n <= 0)
        return;

#ifdef USE_CC
    if (*(u32 *)(k + K_DEV) == 2 && k[K_ERR] == 0) {
        add |= cc_buttons(*(u32 *)(k + K_CLHOLD));
        sx = *(float *)(k + CL_LSTICK);
        sy = *(float *)(k + CL_LSTICK + 4);
        used = 1;
    }
#endif
#ifdef USE_GC
    if (!used && chan < 4 && c->valid) {
        add |= gc_buttons(*(u16 *)c->pad);
        sx = (float)(s8)c->pad[2] / 72.0f;  /* clamped stick: +-72 at the octagon's corners */
        sy = (float)(s8)c->pad[3] / 72.0f;
        used = 1;
    }
#endif
    if (!used)
        return;

    /* the remote, held sideways, tilted by the stick: full stick is about 60 degrees */
    sx = clamp1(dz(sx) * 0.87f);
    sy = clamp1(dz(sy) * 0.87f);
    ax = -sy;                       /* lean forward / back */
    az = -sx;                       /* steer left / right */
    ay = 1.0f - ax * ax - az * az;
    ay = -sqrtf_(ay > 0 ? ay : 0);

    for (i = 0; i < n; i++) {
        u8 *s = k + i * KPAD_SIZE;
        *(u32 *)(s + K_HOLD) |= add;
        ((float *)(s + K_ACC))[0] = ax;
        ((float *)(s + K_ACC))[1] = ay;
        ((float *)(s + K_ACC))[2] = az;
    }
}
