/* GameCube controller and Classic Controller support for Sonic and the Secret Rings.
 *
 * The game reads the GameCube pads itself (PADRead, every frame) and turns each channel's
 * input into one record per frame, but in one of two ways:
 *
 *   - remote mode (a Wii Remote is connected): from the remote's KPAD statuses.  The pad is
 *     ignored, and so is a Classic Controller on the remote.  Story mode steers by tilting the
 *     sideways remote and reads a shake as large accelerometer values.
 *   - pad mode (no Wii Remote): from the GameCube pad, with a button layout and stick handling
 *     the menus and story mode do not understand.
 *
 * Two hooks make a pad behave like a remote in both:
 *
 *   HOOK_REMOTE  just before the remote-mode converter: rewrites the KPAD statuses so they read
 *                as the remote doing what the pad / Classic Controller does.  The game then runs
 *                them through its own smoothing exactly as it does for a real remote.
 *   HOOK_PAD     right after the pad-mode converter: rewrites the record it produced into the
 *                record remote mode would have produced (GameCube controller only).
 *
 * In both: the buttons become the remote buttons they stand for, the left stick tilts the
 * remote (left / right steers, forward / back leans) and the C-stick (Classic Controller:
 * right stick) shakes it.  The remote's own buttons keep working; its motion is replaced while
 * a pad is in use, so a remote lying on the table does not steer.
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
#define K_CLSTICK 0x6C      /* left stick x, y; the right stick follows */
#define K_ERR     0x85

/* PADStatus */
#define P_ERR     10
#define PAD_ERR_TRANSFER (-3)

/* the hook's own variables, inside its body (zero when installed) */
struct state {
    u8 pad[4][12];  /* per port: the last PADStatus that arrived without an error */
    u8 valid[4];
    u32 tick;       /* frames, for the shake's back-and-forth */
};

/* what the player is doing, whichever controller it came from */
struct in {
    u32 btn;        /* WM_* */
    float sx, sy;   /* left stick, -1..1 */
    float cx, cy;   /* C-stick / right stick, -1..1 */
};

/* the record the game keeps per channel per frame (0x38 bytes) */
struct rec {
    u32 hold, nhold, trig, rel;
    float tilt[3];  /* -acc.x, -acc.z, acc.y of the remote, averaged */
    float f7, f8, f9, f10, f11;
    u32 f12, flags;
};

static inline float absf(float v)
{
    return v < 0 ? -v : v;
}

static inline float clamp1(float v)
{
    return v > 1.0f ? 1.0f : v < -1.0f ? -1.0f : v;
}

/* a stick axis with the dead zone removed and a gentle curve near the centre */
static float curve(float v)
{
    const float d = 0.12f;
    float a = absf(v);
    if (a <= d)
        return 0.0f;
    a = (a - d) / (1.0f - d);
    if (a > 1.0f)
        a = 1.0f;
    a = a * (0.35f + 0.65f * a);
    return v < 0 ? -a : a;
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

/* the remote's accelerometer for this input: tilted by the left stick (full stick is about 45
 * degrees), or shaken back and forth while the C-stick is pushed (what a real shake reads as) */
static void accel(const struct in *v, u32 tick, float *ax, float *ay, float *az)
{
    const float tilt = 0.72f;
    float x, z, y;
    if (absf(v->cx) > 0.5f || absf(v->cy) > 0.5f) {
        float s = (tick & 1) ? 1.0f : -1.0f;
        *ax = 3.4f * s;
        *ay = 2.4f * s;
        *az = -3.4f * s;
        return;
    }
    x = -curve(v->sy) * tilt;       /* lean forward / back */
    z = -curve(v->sx) * tilt;       /* steer left / right */
    y = 1.0f - x * x - z * z;
    *ax = x;
    *ay = -sqrtf_(y > 0 ? y : 0);
    *az = z;
}

#ifdef USE_GC
/* keep port `chan`'s last good response; 1 while a pad is plugged in */
static int gc_get(struct state *st, const u8 *pad, u32 chan, struct in *v)
{
    s8 err = (s8)pad[P_ERR];
    u8 *c;
    u32 b, o = 0, i;

    if (chan >= 4)
        return 0;
    c = st->pad[chan];
    if (err == 0) {                         /* PAD_ERR_NONE: a fresh response */
        for (i = 0; i < 12; i++)
            c[i] = pad[i];
        st->valid[chan] = 1;
    } else if (err != PAD_ERR_TRANSFER) {   /* "nothing new yet" keeps the last one */
        st->valid[chan] = 0;
    }
    if (!st->valid[chan])
        return 0;

    b = *(u16 *)c;
    if (b & PAD_A) o |= WM_2;
    if (b & PAD_B) o |= WM_1;
    if (b & PAD_X) o |= WM_A;
    if (b & PAD_Y) o |= WM_B;
    if (b & PAD_L) o |= WM_UP;              /* step left */
    if (b & PAD_R) o |= WM_DOWN;            /* step right */
    if (b & PAD_START) o |= WM_PLUS;
    if (b & PAD_Z) o |= WM_MINUS;
    /* the D-pad as it sits on a sideways remote */
    if (b & PAD_UP) o |= WM_RIGHT;
    if (b & PAD_DOWN) o |= WM_LEFT;
    if (b & PAD_LEFT) o |= WM_UP;
    if (b & PAD_RIGHT) o |= WM_DOWN;
    v->btn = o;
    /* PADClamp'd sticks: about +-72 at the corners of the octagon, +-59 for the C-stick */
    v->sx = clamp1((float)(s8)c[2] / 72.0f);
    v->sy = clamp1((float)(s8)c[3] / 72.0f);
    v->cx = clamp1((float)(s8)c[4] / 59.0f);
    v->cy = clamp1((float)(s8)c[5] / 59.0f);
    return 1;
}
#endif

#ifdef HOOK_REMOTE
#ifdef USE_CC
static int cc_get(const u8 *k, struct in *v)
{
    u32 b, o = 0;
    if (*(u32 *)(k + K_DEV) != 2 || k[K_ERR] != 0)
        return 0;
    b = *(u32 *)(k + K_CLHOLD);
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
    v->btn = o;
    v->sx = ((float *)(k + K_CLSTICK))[0];
    v->sy = ((float *)(k + K_CLSTICK))[1];
    v->cx = ((float *)(k + K_CLSTICK))[2];
    v->cy = ((float *)(k + K_CLSTICK))[3];
    return 1;
}
#endif

/* k: this channel's KPAD statuses (k[0] the newest), n of them; pad: its PADStatus */
void pad_remote(u8 *k, s32 n, u8 *pad, u32 chan, struct state *st)
{
    struct in v;
    int used = 0;
    float ax, ay, az;
    s32 i;

    (void)pad;
    (void)chan;
    st->tick++;
#ifdef USE_GC
    used = gc_get(st, pad, chan, &v);       /* runs every frame to keep the cache fresh */
#endif
    if (n <= 0)
        return;
#ifdef USE_CC
    if (cc_get(k, &v))                      /* a Classic Controller wins over the pad */
        used = 1;
#endif
    if (!used)
        return;

    accel(&v, st->tick, &ax, &ay, &az);
    for (i = 0; i < n; i++) {
        u8 *s = k + i * KPAD_SIZE;
        *(u32 *)(s + K_HOLD) |= v.btn;
        ((float *)(s + K_ACC))[0] = ax;
        ((float *)(s + K_ACC))[1] = ay;
        ((float *)(s + K_ACC))[2] = az;
    }
}
#endif

#ifdef HOOK_PAD
/* the remote mode converter's button bits */
static u32 game_bits(u32 b)
{
    u32 o = 0;
    if (b & WM_UP) o |= 0x10;
    if (b & WM_DOWN) o |= 0x20;
    if (b & WM_RIGHT) o |= 0x80;
    if (b & WM_LEFT) o |= 0x40;
    if (b & WM_A) o |= 0x01;
    if (b & WM_B) o |= 0x02;
    if (b & WM_2) o |= 0x04;
    if (b & WM_1) o |= 0x08;
    if (b & WM_MINUS) o |= 0x88000;
    if (b & WM_HOME) o |= 0x100000;
    if (b & WM_PLUS) o |= 0x4000;
    return o;
}

/* r: the record the pad-mode converter just wrote from pad (this channel's PADStatus);
 * k: the channel's KPAD status buffer, which pad mode leaves untouched from frame to frame */
void pad_only(struct rec *r, u8 *pad, u32 chan, struct state *st, u8 *k)
{
    struct in v;
    u32 prev, hold, x;
    float ax, ay, az, one;

    st->tick++;
    if (!gc_get(st, pad, chan, &v))
        return;

    /* the game's controller manager pauses a story stage with "Communications with the Wii
     * Remote have been interrupted" unless the channel's newest KPAD status reads as a remote
     * without errors: make it one (a bare remote, no extension) */
    k[K_ERR] = 0;
    *(u32 *)(k + K_DEV) = 0;

    /* the converter computed press / release against last frame's word, which this hook wrote:
     * (hold & ~trig) | release gives that word back exactly */
    prev = (r->hold & ~r->trig) | r->rel;
    hold = game_bits(v.btn);
    x = prev ^ hold;
    r->hold = hold;
    r->nhold = ~hold;
    r->trig = hold & x;
    r->rel = prev & x;

    one = r->tilt[2];                       /* the converter's "nothing" value */
    accel(&v, st->tick, &ax, &ay, &az);
    r->tilt[0] = -ax;
    r->tilt[1] = -az;
    r->tilt[2] = ay;
    r->f7 = r->f8 = r->f9 = one;            /* no Nunchuk */
    r->flags |= 0x8000;                     /* the player reads it as a remote, not as sticks */
    if (hold || absf(v.sx) > 0.12f || absf(v.sy) > 0.12f)
        r->flags |= 4;                      /* input this frame (keeps the demo from starting) */
}
#endif
